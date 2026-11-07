"""
Offline regression tests. Small API doubles are used when Checkmk is absent.

Transport, collector and check behavior are tested; doubles do not prove that
Checkmk can load the package. Run discovery on the target site as documented.
"""
import ast
import copy
from datetime import datetime, timezone
from enum import Enum
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import sys
import socket
import tarfile
import types
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / 'cmk_addons_plugins' / 'fortianalyzer'


def load(name, path):
    """
    Load a Python module from a source file, including extensionless agents.

    Input:
        name: Name assigned to the object being created.
        path: Path to the Python source file.

    Output:
        Imported module object after executing its source.

    """
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


try:
    importlib.import_module('cmk.agent_based.v2')
except ImportError:
    class State(Enum):
        """
        Offline stand-in for Checkmk monitoring states.

        Input:
            Constructor arguments supported by the base class.

        Output:
            State instance.

        """
        OK = 0
        WARN = 1
        CRIT = 2
        UNKNOWN = 3

        @classmethod
        def worst(cls, *states):
            """
            Select the worst monitoring state using the Checkmk state ordering.

            Input:
                states: Monitoring states to compare.

            Output:
                Worst state, with CRIT ranked above UNKNOWN.

            """
            order = (cls.OK, cls.WARN, cls.UNKNOWN, cls.CRIT)
            return max(states, key=order.index)

    class Record:
        """
        Attribute container used by the offline Checkmk API doubles.

        Input:
            **kwargs: Attributes stored on the record.

        Output:
            Record instance.

        """
        def __init__(self, **kwargs):
            """
            Initialize the Record instance.

            Input:
                kwargs: Attribute names and values stored on the test double.

            Output:
                None; initializes instance attributes for subsequent operations.

            """
            self.__dict__.update(kwargs)

    class Metric(Record):
        """
        Offline Checkmk metric record containing a name and value.

        Input:
            name: Name assigned to the object being created.
            value: Raw value to validate or convert.
            **kwargs: Attributes stored on the record.

        Output:
            Metric instance.

        """
        def __init__(self, name, value, **kwargs):
            """
            Initialize the Metric instance.

            Input:
                name: Name assigned to the object being created.
                value: Raw value to validate or convert.
                kwargs: Attribute names and values stored on the test double.

            Output:
                None; initializes instance attributes for subsequent operations.

            """
            super().__init__(name=name, value=value, **kwargs)

    class Result(Record):
        """
        Offline Checkmk result record containing state and output text.

        Input:
            Constructor arguments supported by the base class.

        Output:
            Result instance.

        """
        pass

    def check_levels(value, levels_upper=None, levels_lower=None, metric_name=None, label='', render_func=str, **kwargs):
        """
        Apply fixed warning and critical levels in the offline API double.

        Input:
            value: Raw value to validate or convert.
            levels_upper: Upper warning and critical levels in Checkmk format.
            levels_lower: Lower warning and critical levels in Checkmk format.
            metric_name: Metric name, or None to omit the metric.
            label: Human-readable label for the output.
            render_func: Callable formatting the measured value for the summary.
            kwargs: Additional keyword arguments forwarded to the operation.

        Output:
            Yields a Result and, when requested, a Metric for the supplied value.

        """
        state = State.OK
        for levels, lower in ((levels_upper, False), (levels_lower, True)):
            if levels and levels[0] == 'fixed':
                warn, crit = levels[1]
                if (value < crit if lower else value >= crit):
                    state = State.worst(state, State.CRIT)
                elif (value < warn if lower else value >= warn):
                    state = State.worst(state, State.WARN)
        yield Result(state=state, summary=f'{label}: {render_func(value)}' if label else render_func(value))
        if metric_name:
            yield Metric(metric_name, value)

    api = types.ModuleType('cmk.agent_based.v2')
    for name, value in {'AgentSection': Record, 'CheckPlugin': Record, 'Metric': Metric,
                        'Result': Result, 'Service': Record, 'State': State,
                        'check_levels': check_levels, 'render': types.SimpleNamespace(
                            percent=lambda v: f'{v:.1f}%', bytes=lambda v: f'{v} B')}.items():
        setattr(api, name, value)
    for name in ('cmk', 'cmk.agent_based'):
        sys.modules[name] = types.ModuleType(name)
    sys.modules['cmk.agent_based.v2'] = api

agent = load('faz_agent', FAMILY / 'libexec' / 'agent_fortianalyzer')
check_types = importlib.import_module('cmk.agent_based.v2')

# Resolve the plugin namespace through the same import link used during development.
sys.path.insert(0, str(ROOT))
from cmk_addons.plugins.fortianalyzer.agent_based import (  # noqa: E402 - Install Checkmk API doubles first.
    fortianalyzer as legacy_checks,
    fortianalyzer_api as api_checks,
    fortianalyzer_system as system_checks,
    fortianalyzer_license as license_checks,
    fortianalyzer_managed as managed_checks,
    fortianalyzer_adoms as adoms_checks,
    fortianalyzer_support as support_checks,
    fortianalyzer_resources as resources_checks,
    fortianalyzer_logvolume as logvolume_checks,
)

CHECK_MODULES = (
    legacy_checks,
    api_checks,
    system_checks,
    license_checks,
    managed_checks,
    adoms_checks,
    support_checks,
    resources_checks,
    logvolume_checks,
)
builder = load('faz_build', ROOT / 'build_mkp.py')

SYSTEM = {'Hostname': 'FAZ-TEST', 'Version': 'v7.6', 'Serial Number': 'test-serial',
          'Platform Type': 'FAZ-VM64', 'Max Number of Admin Domains': 10}
LICENSE = {'current_num_dev': 3, 'max_num_dev': 10,
           'dev_num_count': {'fgt_cnt': {'val': 3}},
           'licenses': {'FMWR': {'status': 'ok', 'txt': 'Support (Expires 2099-06-14)'}}}
RESOURCES = {'cpu_avg': 10, 'disk': 30, 'memory': 50, 'memory_used': 512, 'memory_total': 1024}
STATS = {'devs': [{'vdoms': [{'lograte': 12.5}, {'lograte': 2}]},
                  {'vdoms': [{'lograte': '0'}, {'lograte': 3.25}]}]}
NO_LEVELS = {'upper': ('no_levels', None), 'lower': ('no_levels', None)}


class FakeClient:
    """
    Fixture API client supporting deterministic responses and failures.

    Input:
        replacements: Fixture overrides replacing API responses.

    Output:
        FakeClient instance.

    """
    def __init__(self, replacements=None):
        """
        Initialize the FakeClient instance.

        Input:
            replacements: Fixture overrides replacing API responses.

        Output:
            None; initializes instance attributes for subsequent operations.

        """
        self.replacements = replacements or {}
        self.calls = []
        self.logged_out = False

    def login(self, user, password):
        """
        Record or simulate authentication in the fixture client.

        Input:
            user: Account name used for authentication.
            password: Password used for authentication.

        Output:
            None; updates fixture authentication state or raises the configured error.

        """
        if 'login' in self.replacements:
            raise agent.APIError('Authentication denied')

    def logout(self):
        """
        Record or simulate session cleanup in the fixture client.

        Input:
            Current instance state.

        Output:
            None; updates fixture logout state or raises the configured error.

        """
        self.logged_out = True
        if 'logout' in self.replacements:
            raise agent.APIError('Logout timeout')

    def call(self, url, **kwargs):
        """
        Return a fixture response or simulate a configured API failure.

        Input:
            url: API resource path.
            kwargs: Additional keyword arguments forwarded to the operation.

        Output:
            Deep copy of the fixture response, or raises the configured API error.

        """
        self.calls.append((url, kwargs))
        values = {'/sys/status': SYSTEM, '/gui/sys/license': LICENSE,
                  '/gui/sys/resource/realtime': RESOURCES,
                  '/dvmdb/adom': [{'name': 'empty'}, {'name': 'production / 7.4'}],
                  '/logview/adom/empty/logstats': {'devs': []},
                  '/logview/adom/production%20%2F%207.4/logstats': STATS}
        result = self.replacements.get(url, values.get(url))
        if isinstance(result, str):
            raise agent.APIError(result)
        return copy.deepcopy(result)


def section(client=None):
    """
    Build parsed section data from the fixture API client.

    Input:
        client: Client used to obtain API or SSH data.

    Output:
        Collected section mapping for use by the check tests.

    """
    return agent.collect(client or FakeClient(), 'test-user', 'test-password')


def metrics(results):
    """
    Index emitted metrics by their names.

    Input:
        results: Check results or collected section records to process.

    Output:
        Mapping of metric names to their measured values.

    """
    return {r.name: r.value for r in results if isinstance(r, check_types.Metric)}


def states(results):
    """
    Extract monitoring states from emitted results.

    Input:
        results: Check results or collected section records to process.

    Output:
        List of states from Result objects.

    """
    return [r.state for r in results if isinstance(r, check_types.Result)]


class LogstatsTests(unittest.TestCase):
    """
    Regression tests for Logstats.

    Input:
        Test method selected by the unittest runner.

    Output:
        LogstatsTests instance.

    """
    def test_sum_all_devices_and_vdoms(self):
        """
        Verify sum all devices and vdoms.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        self.assertEqual(agent.logstats_data(STATS), {'logs_per_second': 17.75, 'devices': 2, 'vdoms': 4})

    def test_empty_and_real_zero_are_valid(self):
        """
        Verify empty and real zero are valid.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        self.assertEqual(agent.logstats_data({'devs': []}), {'logs_per_second': 0, 'devices': 0, 'vdoms': 0})
        self.assertEqual(agent.logstats_data({'devs': [{'vdoms': [{'lograte': 0}]}]})['logs_per_second'], 0)

    def test_missing_fields_never_become_zero(self):
        """
        Verify missing fields never become zero.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        for data in ({}, {'devs': None}, {'devs': [{}]}, {'devs': [{'vdoms': None}]},
                     {'devs': [{'vdoms': [{'lograte': None}]}]}, {'devs': [None]}):
            with self.subTest(data=data), self.assertRaises(agent.APIError):
                agent.logstats_data(data)

    def test_invalid_rates_are_rejected(self):
        """
        Verify invalid rates are rejected.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        for rate in (None, True, 'nan', 'inf', -1, {}, 'bad'):
            with self.subTest(rate=rate), self.assertRaises(agent.APIError):
                agent.logstats_data({'devs': [{'vdoms': [{'lograte': rate}]}]})

    def test_overflow_rejected(self):
        """
        Verify overflow rejected.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        with self.assertRaises(agent.APIError):
            agent.logstats_data({'devs': [{'vdoms': [{'lograte': 1e308}, {'lograte': 1e308}]}]})


class CollectorTests(unittest.TestCase):
    """
    Regression tests for Collector.

    Input:
        Test method selected by the unittest runner.

    Output:
        CollectorTests instance.

    """
    def test_api_version_encoding_logout_and_no_raw_device_data(self):
        """
        Verify API version encoding logout and no raw device data.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        client = FakeClient()
        data = section(client)
        self.assertTrue(client.logged_out)
        self.assertEqual(data['api']['errors'], [])
        self.assertEqual(data['adoms']['data']['production / 7.4'], {'logs_per_second': 17.75, 'devices': 2, 'vdoms': 4})
        self.assertIn(('/logview/adom/production%20%2F%207.4/logstats', {'apiver': 3}), client.calls)

    def test_partial_failure_preserves_good_adom_but_total_has_no_metric(self):
        """
        Verify partial failure preserves good ADOM but total has no metric.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        data = section(FakeClient({'/logview/adom/empty/logstats': 'Timeout'}))
        self.assertEqual([s.item for s in adoms_checks.discover_adoms(data)], ['empty', 'production / 7.4'])
        self.assertEqual(metrics(list(adoms_checks.check_adoms('production / 7.4', NO_LEVELS, data)))['logs_per_second'], 17.75)
        failed = list(adoms_checks.check_adoms('empty', NO_LEVELS, data))
        self.assertEqual(metrics(failed), {})
        self.assertIn(check_types.State.UNKNOWN, states(failed))
        total = list(adoms_checks.check_total(NO_LEVELS, data))
        self.assertEqual(metrics(total), {})
        self.assertIn(check_types.State.UNKNOWN, states(total))
        self.assertIn(check_types.State.CRIT, states(list(api_checks.check_api(data))))

    def test_malformed_logstats_invalidate_total(self):
        """
        Verify malformed logstats invalidate total.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        data = section(FakeClient({'/logview/adom/empty/logstats': {'devs': [{'vdoms': [{'lograte': None}]}]}}))
        self.assertEqual(metrics(list(adoms_checks.check_total(NO_LEVELS, data))), {})

    def test_empty_adom_list_total_zero(self):
        """
        Verify empty ADOM list total zero.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        data = section(FakeClient({'/dvmdb/adom': []}))
        self.assertEqual(list(adoms_checks.discover_adoms(data)), [])
        self.assertEqual(metrics(list(adoms_checks.check_total(NO_LEVELS, data))), {'logs_per_second': 0})

    def test_failed_adom_list_total_unknown(self):
        """
        Verify failed ADOM list total unknown.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        data = section(FakeClient({'/dvmdb/adom': 'Denied'}))
        self.assertEqual(list(adoms_checks.discover_adoms(data)), [])
        self.assertEqual(metrics(list(adoms_checks.check_total(NO_LEVELS, data))), {})

    def test_duplicate_adoms_rejected(self):
        """
        Verify duplicate ADOMs rejected.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        data = section(FakeClient({'/dvmdb/adom': [{'name': 'root'}, {'name': 'root'}]}))
        self.assertIn('error', data['adoms'])

    def test_auth_failure_and_logout_failure(self):
        """
        Verify auth failure and logout failure.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        client = FakeClient({'login': True})
        data = section(client)
        self.assertTrue(client.logged_out)
        self.assertEqual(client.calls, [])
        self.assertEqual(metrics(list(adoms_checks.check_total(NO_LEVELS, data))), {})
        data = section(FakeClient({'logout': True}))
        self.assertIn(check_types.State.CRIT, states(list(api_checks.check_api(data))))

    def test_license_failure_does_not_invalidate_good_log_total(self):
        """
        Verify license failure does not invalidate good log total.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        data = section(FakeClient({'/gui/sys/license': 'HTTP 403'}))
        self.assertEqual(metrics(list(adoms_checks.check_total(NO_LEVELS, data))), {'logs_per_second': 17.75})


class CheckTests(unittest.TestCase):
    """
    Regression tests for Check.

    Input:
        Test method selected by the unittest runner.

    Output:
        CheckTests instance.

    """
    def test_lograte_metrics_zero_and_total(self):
        """
        Verify log rate metrics zero and total.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        data = section()
        self.assertEqual(metrics(list(adoms_checks.check_adoms('production / 7.4', NO_LEVELS, data))),
                         {'devices': 2, 'vdoms': 4, 'logs_per_second': 17.75})
        self.assertEqual(metrics(list(adoms_checks.check_adoms('empty', NO_LEVELS, data))),
                         {'devices': 0, 'vdoms': 0, 'logs_per_second': 0})
        self.assertEqual(metrics(list(adoms_checks.check_total(NO_LEVELS, data))), {'logs_per_second': 17.75})

    def test_lograte_thresholds(self):
        """
        Verify log rate thresholds.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        upper = dict(NO_LEVELS, upper=('fixed', (10, 15)))
        self.assertIn(check_types.State.CRIT, states(list(adoms_checks.check_total(upper, section()))))
        lower = dict(NO_LEVELS, lower=('fixed', (10, 1)))
        self.assertIn(check_types.State.CRIT, states(list(adoms_checks.check_adoms('empty', lower, section()))))

    def test_disappeared_adom_unknown(self):
        """
        Verify disappeared ADOM unknown.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        self.assertIn(check_types.State.UNKNOWN, states(list(adoms_checks.check_adoms('removed', NO_LEVELS, section()))))

    def test_invalid_normalized_stats_total_unknown(self):
        """
        Verify invalid normalized stats total unknown.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        for bad in ({'logs_per_second': 0}, {'logs_per_second': -1, 'devices': 1, 'vdoms': 1},
                    {'logs_per_second': 1, 'devices': 0.5, 'vdoms': 1}):
            data = section()
            data['adoms']['data']['empty'] = bad
            self.assertEqual(metrics(list(adoms_checks.check_total(NO_LEVELS, data))), {})

    def test_system_and_managed(self):
        """
        Verify system and managed.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        for item in system_checks.SYSTEM_FIELDS:
            result = list(system_checks.check_system(item, section()))
            self.assertEqual(set(states(result)), {check_types.State.OK})
            self.assertEqual([r.summary for r in result if isinstance(r, check_types.Result)], [str(SYSTEM[item])])
        self.assertEqual(metrics(list(managed_checks.check_managed(section()))), {'faz_logging_devices': 3})
        data = section()
        del data['system']['data']['Hostname']
        self.assertIn(check_types.State.UNKNOWN, states(list(system_checks.check_system('Hostname', data))))
        self.assertEqual(states(list(system_checks.check_system('Version', data))), [check_types.State.OK])

    def test_license_math_and_zero_capacity(self):
        """
        Verify license math and zero capacity.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        params = {'levels': ('fixed', (80, 90))}
        self.assertEqual(metrics(list(license_checks.check_license(params, section()))),
                         {'used_devices': 3, 'licensed_devices': 10, 'free_devices': 7, 'utilization_percent': 30})
        data = section()
        data['license']['data']['max_num_dev'] = 0
        result = list(license_checks.check_license(params, data))
        self.assertIn(check_types.State.CRIT, states(result))
        self.assertNotIn('utilization_percent', metrics(result))

    def test_combined_resources_metrics_summary_thresholds_and_partial_data(self):
        """
        Verify combined resources metrics summary thresholds and partial data.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        params = resources_checks.check_plugin_fortianalyzer_resources_combined.check_default_parameters
        results = list(resources_checks.check_combined_resources(params, section()))
        self.assertEqual(metrics(results), {'faz_cpu_percent': 10, 'faz_disk_percent': 30,
            'faz_memory_percent': 50, 'faz_memory_total': 1024 * 1024,
            'faz_memory_used': 512 * 1024, 'faz_memory_free': 512 * 1024})
        summary = ', '.join(r.summary for r in results if isinstance(r, check_types.Result))
        for label in ('CPU average:', 'Disk usage:', 'Memory usage:', 'Memory:', 'used,', 'free'):
            self.assertIn(label, summary)
        data = section()
        data['resources']['data']['cpu_avg'] = 95
        del data['resources']['data']['memory_used']
        results = list(resources_checks.check_combined_resources(params, data))
        self.assertIn(check_types.State.CRIT, states(results))
        self.assertIn(check_types.State.UNKNOWN, states(results))
        self.assertIn('faz_memory_total', metrics(results))
        self.assertNotIn('faz_memory_used', metrics(results))
        self.assertEqual(metrics(results)['faz_disk_percent'], 30)
        self.assertEqual(resources_checks.check_plugin_fortianalyzer_resources_combined.service_name, 'FortiAnalyzer Resources')
        self.assertEqual(list(resources_checks.discover_retired_resources(data)), [])

    def test_resources_unit_conversion_and_missing_values(self):
        """
        Verify resources unit conversion and missing values.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        params = resources_checks.check_plugin_fortianalyzer_resources.check_default_parameters
        self.assertEqual(metrics(list(resources_checks.check_resources('Memory Used', params, section())))['faz_memory_used'], 512 * 1024)
        self.assertEqual(metrics(list(resources_checks.check_resources('Memory Used', dict(params, memory_unit='gb'), section())))['faz_memory_used'], 512 * 1e9)
        data = section()
        del data['resources']['data']['memory_used']
        result = list(resources_checks.check_resources('Memory Used', params, data))
        self.assertIn(check_types.State.UNKNOWN, states(result))
        self.assertNotIn('faz_memory_used', metrics(result))
        self.assertEqual(metrics(list(resources_checks.check_resources('Memory Total', params, data))), {'faz_memory_total': 1024 * 1024})

    def test_dedicated_sensor_discovery_and_legacy_services(self):
        """
        Verify dedicated sensor discovery and legacy services.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        self.assertEqual([s.item for s in system_checks.discover_system(section())], list(system_checks.SYSTEM_FIELDS))
        self.assertEqual(len(list(resources_checks.discover_resources(section()))), 1)
        self.assertEqual(list(resources_checks.discover_retired_resources(section())), [])
        self.assertIn(check_types.State.UNKNOWN, states(list(system_checks.check_system(None, section()))))
        params = resources_checks.check_plugin_fortianalyzer_resources.check_default_parameters
        self.assertIn(check_types.State.UNKNOWN, states(list(resources_checks.check_resources(None, params, section()))))

    def test_resource_sensors_values_metrics_thresholds_and_isolation(self):
        """
        Verify resource sensors values metrics thresholds and isolation.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        params = resources_checks.check_plugin_fortianalyzer_resources.check_default_parameters
        expected = {'CPU Average': ('faz_cpu_percent', 10), 'Disk Usage': ('faz_disk_percent', 30),
                    'Memory Usage': ('faz_memory_percent', 50), 'Memory Used': ('faz_memory_used', 512 * 1024),
                    'Memory Total': ('faz_memory_total', 1024 * 1024), 'Memory Free': ('faz_memory_free', 512 * 1024)}
        for item, (metric, value) in expected.items():
            result = list(resources_checks.check_resources(item, params, section()))
            self.assertEqual(metrics(result), {metric: value})
            self.assertEqual(set(states(result)), {check_types.State.OK})
            summaries = [r.summary for r in result if isinstance(r, check_types.Result)]
            self.assertEqual(len(summaries), 1)
            self.assertNotIn(':', summaries[0])
        data = section()
        data['resources']['data']['cpu_avg'] = 95
        del data['resources']['data']['memory_used']
        self.assertIn(check_types.State.CRIT, states(list(resources_checks.check_resources('CPU Average', params, data))))
        self.assertEqual(states(list(resources_checks.check_resources('Disk Usage', params, data))), [check_types.State.OK])
        self.assertEqual(metrics(list(resources_checks.check_resources('Memory Free', params, data))), {})

    def test_support_fmwr_fcem_and_expiry(self):
        """
        Verify support fmwr fcem and expiry.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        params = support_checks.check_plugin_fortianalyzer_support.check_default_parameters
        self.assertEqual(set(states(list(support_checks.check_support(params, section())))), {check_types.State.OK})
        data = section()
        data['license']['data']['licenses'] = {'FCEM': {'status': 'ok', 'txt': 'Support (Expires 2099-01-01)'}}
        self.assertEqual(set(states(list(support_checks.check_support(params, data)))), {check_types.State.OK})
        data['license']['data']['licenses']['FCEM']['txt'] = 'Expires 2020-01-01'
        self.assertIn(check_types.State.CRIT, states(list(support_checks.check_support(params, data))))

    def test_parser(self):
        """
        Verify parser.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        data = section()
        self.assertEqual(api_checks.parse_fortianalyzer([[json.dumps(data)]]), data)
        self.assertTrue(api_checks.parse_fortianalyzer([['bad']])['api']['errors'])

    def test_real_root_response_partial_rates_are_visible(self):
        """
        Verify real root response partial rates are visible.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        raw = {'devs': [{'vdoms': vdoms} for vdoms in (
            [{'lograte': 0.266667}], [{}, {'lograte': 0.0}], [{}, {'lograte': 6.5}],
            [{'lograte': 8.1}], [{'lograte': 0.066667}], [{'lograte': 1.1}], [{}],
            [{'lograte': 0.933333}], [{'lograte': 0.0}])]}
        parsed = agent.logstats_data(raw)
        self.assertEqual((parsed['devices'], parsed['vdoms'], parsed['missing_vdoms']), (9, 11, 3))
        self.assertAlmostEqual(parsed['logs_per_second'], 16.966667)
        data = {'adoms': {'data': {'root': parsed}}}
        result = list(adoms_checks.check_adoms('root', NO_LEVELS, data))
        self.assertEqual(set(states(result)), {check_types.State.OK})
        self.assertAlmostEqual(metrics(result)['faz_reported_logs_per_second'], 16.966667)
        self.assertNotIn('logs_per_second', metrics(result))
        total = list(adoms_checks.check_total(NO_LEVELS, data))
        self.assertEqual(set(states(total)), {check_types.State.OK})
        self.assertNotIn('logs_per_second', metrics(total))
        self.assertAlmostEqual(metrics(total)['faz_reported_logs_per_second'], 16.966667)

    def test_all_rates_missing_exports_no_zero_rate(self):
        """
        Verify all rates missing exports no zero rate.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        data = {'adoms': {'data': {'root': agent.logstats_data({'devs': [{'vdoms': [{}]}]})}}}
        result = list(adoms_checks.check_adoms('root', NO_LEVELS, data))
        self.assertIn(check_types.State.UNKNOWN, states(result))
        self.assertEqual(metrics(result), {'devices': 1, 'vdoms': 1})
        self.assertEqual(metrics(list(adoms_checks.check_total(NO_LEVELS, data))), {})

    def test_explicit_adom_exclusions_change_scope(self):
        """
        Verify explicit ADOM exclusions change scope.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        client = FakeClient({'/logview/adom/empty/logstats': 'Server error'})
        data = agent.collect(client, 'test-user', 'test-password', ['empty'])
        self.assertNotIn('/logview/adom/empty/logstats', [url for url, _ in client.calls])
        self.assertEqual(data['adoms']['excluded'], ['empty'])
        self.assertEqual(data['api']['errors'], [])
        total = list(adoms_checks.check_total(NO_LEVELS, data))
        self.assertEqual(metrics(total), {'logs_per_second': 17.75})
        self.assertTrue(any('excluded' in r.summary for r in total if isinstance(r, check_types.Result)))


class TransportTests(unittest.TestCase):
    """
    Regression tests for Transport.

    Input:
        Test method selected by the unittest runner.

    Output:
        TransportTests instance.

    """
    def client(self, payload):
        """
        Create a transport client with the supplied fake response.

        Input:
            payload: API response payload.

        Output:
            API client configured with a mock opener.

        """
        client = agent.Client('fortianalyzer.example')
        self.requests = []

        def respond(request, timeout):
            """
            Supply a deterministic HTTP response for the transport test.

            Input:
                request: HTTP request supplied to the transport double.
                timeout: Maximum wait time in seconds.

            Output:
                Context manager or response double used by the mocked opener.

            """
            self.requests.append(request)
            if isinstance(payload, Exception):
                raise payload
            return io.BytesIO(json.dumps(payload).encode())

        client.opener = types.SimpleNamespace(open=respond)
        return client

    def test_jsonrpc_login_flat_gui_cookie_and_logout(self):
        """
        Verify jsonrpc login flat gui cookie and logout.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        client = self.client({'session': 'test-session', 'result': [{'status': {'code': 0}, 'data': {}}]})
        client.login('test-user', 'test-password')
        self.assertEqual(json.loads(self.requests[-1].data)['params'][0]['data']['passwd'], 'test-password')
        client.call('/gui/sys/license', gui=True)
        self.assertEqual(json.loads(self.requests[-1].data), {'method': 'get', 'url': '/gui/sys/license'})
        self.assertEqual(self.requests[-1].get_header('Cookie'), 'CURRENT_SESSION=test-session')
        client.logout()
        self.assertEqual(json.loads(self.requests[-1].data)['params'][0]['url'], '/sys/logout')
        self.assertIsNone(client.session)

    def test_logview_object_result_without_status(self):
        """
        Verify logview object result without status.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        client = self.client({'jsonrpc': '2.0', 'id': 2, 'result': {'data': STATS}})
        self.assertEqual(client.call('/logview/adom/root/logstats', apiver=3), STATS)
        body = json.loads(self.requests[-1].data)
        self.assertEqual(body['params'], [{'url': '/logview/adom/root/logstats', 'apiver': 3}])
        self.assertEqual(body['jsonrpc'], '2.0')

    def test_missing_status_only_allowed_for_logstats(self):
        """
        Verify missing status only allowed for logstats.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        client = self.client({'result': {'data': STATS}})
        with self.assertRaises(agent.APIError):
            client.call('/sys/status')

    def test_explicit_errors_are_never_success(self):
        """
        Verify explicit errors are never success.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        for payload in ({'error': {'code': -1}}, {'result': {'error': {'code': -1}, 'data': STATS}},
                        {'result': {'status': {'code': -11}, 'data': STATS}},
                        {'result': {'status': None, 'data': STATS}}, {'result': {'data': None}}):
            with self.subTest(payload=payload), self.assertRaises(agent.APIError):
                self.client(payload).call('/logview/adom/root/logstats', apiver=3)

    def test_http_timeout_and_no_leaked_server_messages(self):
        """
        Verify http timeout and no leaked server messages.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        for error in (HTTPError('https://example', 401, 'sensitive', {}, None), URLError('sensitive'), TimeoutError('sensitive')):
            with self.subTest(error=error), self.assertRaises(agent.APIError) as context:
                self.client(error).call('/test')
            self.assertNotIn('sensitive', str(context.exception))

    def test_login_without_session_fails(self):
        """
        Verify login without session fails.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        with self.assertRaises(agent.APIError):
            self.client({'result': [{'status': {'code': 0}}]}).login('user', 'password')

    def test_jsonrpc_error_code_preserved_without_server_message(self):
        """
        Verify jsonrpc error code preserved without server message.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        with self.assertRaises(agent.APIError) as context:
            self.client({'error': {'code': -32005, 'message': 'sensitive'}}).call('/logview/adom/others/logstats', apiver=3)
        self.assertIn('-32005', str(context.exception))
        self.assertNotIn('sensitive', str(context.exception))


class PackageTests(unittest.TestCase):
    """
    Regression tests for Package.

    Input:
        Test method selected by the unittest runner.

    Output:
        PackageTests instance.

    """
    def test_rule_migration_removes_address_and_ca_overrides(self):
        """
        Migrate saved rules without retaining removed address or CA bundle settings.

        Input:
            Legacy rule settings with address, CA bundle and SSH options.

        Output:
            None; assertions verify migration, input preservation and form fields.

        """
        tree = ast.parse((FAMILY / 'rulesets' / 'special_agent.py').read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        namespace = {}
        exec(compile(ast.Module(body=[node for node in functions if node.name.startswith('migrate_')],
                                type_ignores=[]), '<rule migration>', 'exec'), namespace)
        original = {
            'user': 'monitoring', 'password': 'password-reference',
            'address': 'old-target.example', 'port': 8443,
            'ca_file': '/obsolete/ca-bundle.pem',
            'ssh_logvolume': {'port': 2222, 'address': 'old-ssh.example'},
        }
        snapshot = copy.deepcopy(original)
        migrated = namespace['migrate_password_fields'](original)
        self.assertEqual(original, snapshot)
        self.assertNotIn('address', migrated)
        self.assertNotIn('ca_file', migrated)
        self.assertEqual(migrated['authentication'], ('password', {
            'user': original['user'], 'password': original['password']}))
        self.assertEqual(migrated['port'], 8443)
        self.assertEqual(migrated['ssh_logvolume'], {'port': 2222})
        form = next(node for node in functions if node.name == 'parameter_form')
        dictionary = next(node.value for node in form.body if isinstance(node, ast.Return))
        elements = next(keyword.value for keyword in dictionary.keywords if keyword.arg == 'elements')
        self.assertNotIn('address', [ast.literal_eval(key) for key in elements.keys])
        self.assertNotIn('ca_file', [ast.literal_eval(key) for key in elements.keys])

    def test_agent_target_uses_host_configuration(self):
        """
        Ignore removed overrides and resolve the target from the Checkmk host.

        Input:
            Host configurations with or without a primary address and a saved override.

        Output:
            None; assertions verify API and SSH command arguments and secret identity.

        """
        api = types.ModuleType('cmk.server_side_calls.v1')
        api.Secret = type('Secret', (), {})
        api.SpecialAgentCommand = lambda **kwargs: types.SimpleNamespace(**kwargs)
        api.SpecialAgentConfig = lambda **kwargs: types.SimpleNamespace(**kwargs)
        api.noop_parser = lambda value: value
        with patch.dict(sys.modules, {'cmk.server_side_calls.v1': api}):
            calls = load('faz_command_test', FAMILY / 'server_side_calls' / 'fortianalyzer.py')
        secret = api.Secret()
        params = {
            'user': 'monitoring', 'password': secret, 'address': 'old-target.example',
            'ca_file': '/obsolete/ca-bundle.pem',
            'ssh_logvolume': {'port': 2222},
        }
        for primary, expected in (('192.0.2.10', '192.0.2.10'), ('', 'faz.example')):
            with self.subTest(primary=primary):
                host = types.SimpleNamespace(
                    primary_ip_config=types.SimpleNamespace(address=primary), name='faz.example',
                )
                command, = calls.commands(params, host)
                args = command.command_arguments
                self.assertEqual(args[:2], ['--address', expected])
                self.assertNotIn('old-target.example', args)
                self.assertNotIn('--ca-file', args)
                self.assertNotIn('/obsolete/ca-bundle.pem', args)
                self.assertNotIn('--no-cert-check', args)
                self.assertIs(args[args.index('--password-id') + 1], secret)
                self.assertIn('--ssh-logvolume', args)
                self.assertEqual(args[args.index('--ssh-port') + 1], '2222')
                self.assertEqual(args.count('--address'), 1)

    def test_new_rule_exclusion_defaults_preserve_existing_rules(self):
        """
        Support both form constructors and retain saved exclusion settings.

        Input:
            Checkmk 2.4 and 2.5 extended-form constructor contracts and saved rules.

        Output:
            None; assertions verify the requested defaults and migration behavior.

        """
        from dataclasses import make_dataclass

        expected = ['FortiAnalyzer', 'FortiAuthenticator', 'FortiCache', 'FortiCarrier', 'FortiClient', 'FortiDDoS', 'FortiDeceptor', 'FortiFirewall', 'FortiFirewallCarrier', 'FortiMail', 'FortiManager', 'FortiProxy', 'FortiSandbox', 'FortiWeb', 'Syslog', 'Unmanaged_Devices', 'others', 'rootp']
        tree = ast.parse((FAMILY / 'rulesets' / 'special_agent.py').read_text())
        definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef) or (
            isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and
            target.id == 'DEFAULT_EXCLUDED_ADOMS' for target in node.targets))]
        namespace = {
            'Title': str, 'Help': str,
            'DefaultValue': lambda value: types.SimpleNamespace(value=value),
            'DictElement': lambda parameter_form, required=False: types.SimpleNamespace(
                parameter_form=parameter_form, required=required),
            'validators': types.SimpleNamespace(
                LengthInRange=lambda **kwargs: None, NetworkPort=lambda: None,
                NumberInRange=lambda **kwargs: None),
            'migrate_to_password': lambda value: value,
        }
        for name in ('Dictionary', 'Integer', 'Password', 'SingleChoice', 'SingleChoiceElement', 'String',
                     'CascadingSingleChoice', 'CascadingSingleChoiceElement'):
            namespace[name] = lambda **kwargs: types.SimpleNamespace(**kwargs)
        namespace['ListExtended'] = make_dataclass('ListExtended',
            ['title', 'element_template', 'prefill', 'help_text'], kw_only=True)
        for version, extra in (('2.4', []), ('2.5', ['default_checked'])):
            with self.subTest(version=version):
                namespace['DictionaryExtended'] = make_dataclass('DictionaryExtended',
                    ['elements', 'migrate', *extra], kw_only=True)
                exec(compile(ast.Module(body=definitions, type_ignores=[]), '<rule forms>', 'exec'), namespace)
                form = namespace['parameter_form']()
                authentication = form.elements['authentication']
                self.assertTrue(authentication.required)
                choice = authentication.parameter_form
                self.assertEqual(choice.title, 'Authentication method')
                self.assertEqual(choice.prefill.value, 'password')
                admin, token = choice.elements
                self.assertEqual((admin.name, admin.title), ('password', 'Admin user'))
                self.assertEqual(set(admin.parameter_form.elements), {'user', 'password'})
                for field, title in (('user', 'API user name'), ('password', 'API password')):
                    element = admin.parameter_form.elements[field]
                    self.assertTrue(element.required)
                    self.assertEqual(element.parameter_form.title, title)
                self.assertEqual((token.name, token.title), ('token', 'API user'))
                self.assertEqual(token.parameter_form.title, 'API token')
                self.assertNotIn('user', form.elements)
                self.assertNotIn('password', form.elements)
                option = form.elements['exclude_adoms']
                self.assertFalse(option.required)
                self.assertEqual(option.parameter_form.prefill.value, expected)
                if version == '2.4':
                    self.assertEqual(namespace['_new_rule_defaults'](), {})
                else:
                    self.assertEqual(form.default_checked, ['exclude_adoms'])
                for saved in ({'user': 'monitoring'}, {'exclude_adoms': []},
                              {'exclude_adoms': ['custom-adom']}):
                    original = copy.deepcopy(saved)
                    self.assertEqual(form.migrate(saved), original)
                    self.assertEqual(saved, original)
                option.parameter_form.prefill.value.clear()
                self.assertEqual(namespace['parameter_form']().elements[
                    'exclude_adoms'].parameter_form.prefill.value, expected)

    def test_split_plugin_registrations(self):
        """
        Verify that all check plugins and the shared parser register exactly once.

        Input:
            Feature modules imported through the Checkmk plugin namespace.

        Output:
            None; assertions fail for missing, duplicate or misplaced registrations.

        """
        expected = {
            'fortianalyzer_api', 'fortianalyzer_system', 'fortianalyzer_license',
            'fortianalyzer_managed', 'fortianalyzer_adoms', 'fortianalyzer_total',
            'fortianalyzer_support', 'fortianalyzer_resources',
            'fortianalyzer_resources_combined', 'fortianalyzer_adom_logvolume',
            'fortianalyzer_total_logvolume',
        }
        registrations = [
            (module, plugin)
            for module in CHECK_MODULES
            for name, plugin in vars(module).items()
            if name.startswith('check_plugin_')
        ]
        self.assertCountEqual([plugin.name for _, plugin in registrations], expected)
        for module, plugin in registrations:
            self.assertEqual(plugin.sections, ['fortianalyzer'])
            self.assertEqual(plugin.check_function.__module__, module.__name__)
            self.assertTrue(callable(plugin.discovery_function))
        sections = [
            section
            for module in CHECK_MODULES
            for name, section in vars(module).items()
            if name.startswith('agent_section_')
        ]
        self.assertEqual([section.name for section in sections], ['fortianalyzer'])
        self.assertIs(sections[0].parse_function, api_checks.parse_fortianalyzer)

    def test_precompiled_legacy_imports(self):
        """
        Run imports using the module path retained by previously compiled checks.

        Input:
            A compiled import statement using the historical FortiAnalyzer module.

        Output:
            None; assertions verify parser, callback and plugin object identity.

        """
        program = compile(
            'from cmk_addons.plugins.fortianalyzer.agent_based.fortianalyzer import '
            'parse_fortianalyzer, check_api, check_plugin_fortianalyzer_api, '
            'agent_section_fortianalyzer',
            '<previously compiled FortiAnalyzer check>', 'exec',
        )
        namespace = {}
        exec(program, namespace)
        self.assertIs(namespace['parse_fortianalyzer'], api_checks.parse_fortianalyzer)
        self.assertIs(namespace['check_plugin_fortianalyzer_api'],
                      api_checks.check_plugin_fortianalyzer_api)
        self.assertIs(namespace['agent_section_fortianalyzer'], api_checks.agent_section_fortianalyzer)
        data = namespace['parse_fortianalyzer']([[json.dumps({'api': {'errors': []}})]])
        self.assertEqual(states(list(namespace['check_api'](data))), [check_types.State.OK])

    def test_legacy_exports_preserve_identity_without_registration_duplicates(self):
        """
        Verify historical exports without exposing duplicate plugin registrations.

        Input:
            Feature modules and the legacy compatibility module.

        Output:
            None; assertions fail for broken exports or duplicate registrations.

        """
        for module in CHECK_MODULES:
            if module is legacy_checks:
                continue
            for name, value in vars(module).items():
                if name.startswith(('check_plugin_', 'agent_section_')) or (
                    callable(value) and getattr(value, '__module__', '').startswith(
                        'cmk_addons.plugins.fortianalyzer.'
                    )
                ) or name in ('SYSTEM_FIELDS', 'RESOURCE_PERCENTAGES', 'RESOURCE_MEMORY'):
                    with self.subTest(name=name):
                        self.assertIs(getattr(legacy_checks, name), value)
        for name in set(vars(legacy_checks)) | set(dir(legacy_checks)):
            self.assertFalse(name.startswith(('check_plugin_', 'agent_section_')))
        with self.assertRaises(AttributeError):
            getattr(legacy_checks, 'unknown_legacy_attribute')

    def test_reproducible_package_and_manifest(self):
        """
        Verify reproducible package and manifest.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        path = builder.build()
        self.assertEqual(path.name, f'check_fortianalyzer-{builder.VERSION}.mkp')
        with tarfile.open(path, 'r:gz') as outer:
            metadata = json.load(outer.extractfile('info.json'))
            self.assertEqual(metadata['version'], builder.VERSION)
            self.assertEqual(metadata['version.min_required'], '2.4.0')
            self.assertEqual(metadata['version.usable_until'], '2.5.99')
            self.assertEqual(metadata['name'], 'check_fortianalyzer')
            self.assertEqual(metadata['title'], 'FortiAnalyzer')
            self.assertEqual(metadata['author'], 'Mayuran Asairatnam')
            self.assertEqual(metadata, ast.literal_eval(outer.extractfile('info').read().decode()))
            with tarfile.open(fileobj=io.BytesIO(outer.extractfile('cmk_addons_plugins.tar').read())) as inner:
                self.assertEqual(inner.getnames(), metadata['files']['cmk_addons_plugins'])
                self.assertEqual(metadata['num_files'], len(inner.getnames()))
                expected_modules = {
                    'fortianalyzer/agent_based/' + Path(module.__file__).name
                    for module in CHECK_MODULES
                } | {'fortianalyzer/lib/common.py'}
                self.assertTrue(expected_modules.issubset(inner.getnames()))
                self.assertIn('fortianalyzer/agent_based/fortianalyzer.py', inner.getnames())
                self.assertEqual(inner.getmember('fortianalyzer/libexec/agent_fortianalyzer').mode, 0o755)
                self.assertFalse(any('fortimanager' in name or '__pycache__' in name for name in inner.getnames()))
        previous = path.read_bytes()
        builder.build()
        self.assertEqual(previous, path.read_bytes())


class GraphTests(unittest.TestCase):
    """
    Check graph applicability against the metrics emitted by services.

    AST validation avoids replacing the graph API with a permissive mock.
    Loading in a real Checkmk site still requires an installation check.

    Input:
        Test method selected by the unittest runner.

    Output:
        GraphTests instance.

    """
    def graphs(self, family=FAMILY):
        """
        Read graph registrations directly from their Python syntax tree.

        Input:
            family: Plugin family directory containing graph definitions.

        Output:
            Graph declarations extracted without importing the Checkmk graphing API.

        """
        tree = ast.parse((family / 'graphing' / (family.name + '.py')).read_text())
        graphs = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            if not isinstance(node.value.func, ast.Name) or node.value.func.id != 'Graph':
                continue
            self.assertTrue(node.targets[0].id.startswith('graph_'))
            args = {kw.arg: kw.value for kw in node.value.keywords}
            name = ast.literal_eval(args['name'])
            self.assertNotIn(name, graphs)
            graphs[name] = {key: set(ast.literal_eval(args[key])) if key in args else set()
                            for key in ('simple_lines', 'compound_lines', 'optional', 'conflicting')}
        return graphs

    def test_graphs_cover_service_metrics_and_partial_resources(self):
        """
        Verify graphs cover service metrics and partial resources.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        graphs = self.graphs()
        metric_tree = ast.parse((FAMILY / 'graphing' / (FAMILY.name + '.py')).read_text())
        metrics = set()
        for node in ast.walk(metric_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Metric':
                metrics.add(next(ast.literal_eval(kw.value) for kw in node.keywords if kw.arg == 'name'))
        # License counts are emitted together. Other measurements need graphs
        # even when a neighbouring resource measurement is missing/invalid.
        cases = [{'used_devices', 'licensed_devices', 'free_devices', 'utilization_percent'}]
        cases += [{name} for name in metrics - {'used_devices', 'licensed_devices', 'free_devices'}]
        cases += [{'devices', 'vdoms'}] if FAMILY.name == 'fortianalyzer' else [{'devices'}]
        for emitted in cases:
            with self.subTest(emitted=emitted):
                applicable = [g for g in graphs.values()
                              if not g['conflicting'] & emitted
                              and (g['simple_lines'] | g['compound_lines']) - g['optional'] <= emitted]
                covered = set().union(*(g['simple_lines'] | g['compound_lines'] for g in applicable))
                self.assertTrue(emitted <= covered, emitted - covered)

    def assert_unique_graph_and_metric_definition_names(self, paths):
        """
        Verify unique graph, metric and perfometer names across given files.
        """
        names = {'Graph': set(), 'Metric': set(), 'Perfometer': set()}
        for path in paths:
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names:
                    name = next(ast.literal_eval(kw.value) for kw in node.keywords if kw.arg == 'name')
                    self.assertNotIn(name, names[node.func.id])
                    names[node.func.id].add(name)

    def test_unique_graph_and_metric_definition_names(self):
        self.assert_unique_graph_and_metric_definition_names([
            FAMILY / 'graphing' / 'fortianalyzer.py',
        ])

    def test_both_packages_have_unique_graph_and_metric_definition_names(self):
        other = ROOT.parent / 'check_fortimanager' / 'cmk_addons_plugins' / 'fortimanager' / 'graphing' / 'fortimanager.py'
        if not other.is_file():
            self.skipTest('Optional sibling FortiManager project is not available')
        self.assert_unique_graph_and_metric_definition_names([
            FAMILY / 'graphing' / 'fortianalyzer.py', other,
        ])


class LogVolumeTests(unittest.TestCase):
    """
    Regression tests for LogVolume.

    Input:
        Test method selected by the unittest runner.

    Output:
        LogVolumeTests instance.

    """
    def fixture(self):
        """
        Build a dated CLI log-volume response for the tests.

        Input:
            None.

        Output:
            CLI response string containing representative volume values.

        """
        today = datetime.now(timezone.utc).date().isoformat()
        return (f"FAZ # diagnose fortilogd logvol-adom all\n{today} 2026-07-20 average\n"
                "adom 'root':\n 0 B 0 B 0 B\n"
                "adom 'FWAAS_MGMT':\n 3.15 MB 8.53 MB 5.84 MB\n")

    def test_dates_units_zero_and_average(self):
        """
        Verify dates units zero and average.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        rows = agent.parse_logvolume(self.fixture())
        self.assertEqual(rows['root']['gb_day'], 0)
        self.assertAlmostEqual(rows['FWAAS_MGMT']['gb_day'], 3.15 * 1024**2 / 1e9)
        self.assertAlmostEqual(rows['FWAAS_MGMT']['average_gb_day'], 5.84 * 1024**2 / 1e9)
        self.assertEqual(len(rows['root']['history']), 2)

    def test_malformed_output_never_becomes_zero(self):
        """
        Verify malformed output never becomes zero.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        for text in ('Permission denied', self.fixture().replace('3.15 MB', '-3.15 MB'),
                     self.fixture().replace('3.15 MB', 'NaN MB'), self.fixture() + "adom 'broken':\n",
                     self.fixture() + "adom 'root':\n0 B 0 B 0 B\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                agent.parse_logvolume(text)

    def test_ssh_fixed_command_host_verification_exclusions_and_errors(self):
        """
        Verify ssh fixed command host verification exclusions and errors.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        with patch.object(agent.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout=self.fixture())) as run:
            result = agent.collect_logvolume('faz.example', 'monitor', '/site/key', known_hosts='/site/hosts', excluded=['root'])
            self.assertEqual(set(result['data']), {'FWAAS_MGMT'})
            self.assertEqual(result['excluded'], ['root'])
            args = run.call_args.args[0]
            self.assertEqual(args[-1], 'diagnose fortilogd logvol-adom all')
            self.assertIn('StrictHostKeyChecking=yes', args)
            self.assertIn('BatchMode=yes', args)
            self.assertNotIn('shell', run.call_args.kwargs)
        with patch.object(agent.subprocess, 'run') as run:
            self.assertIn('error', agent.collect_logvolume('-oProxyCommand=bad', 'monitor', '/site/key'))
            run.assert_not_called()
        for failure in (OSError('sensitive'), agent.subprocess.TimeoutExpired('ssh', 1)):
            with patch.object(agent.subprocess, 'run', side_effect=failure):
                result = agent.collect_logvolume('faz.example', 'monitor', '/site/key')
                self.assertIn('error', result)
                self.assertNotIn('sensitive', result['error'])

    def test_discovery_totals_thresholds_and_stale_data(self):
        """
        Verify discovery totals thresholds and stale data.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        data = {'logvolume': {'data': agent.parse_logvolume(self.fixture())}}
        self.assertEqual(list(logvolume_checks.discover_logvolume(data)), [])
        self.assertEqual(list(logvolume_checks.discover_total_logvolume(data)), [])
        total = list(logvolume_checks.check_total_logvolume({'levels': ('fixed', (0.001, 0.002))}, data))
        self.assertIn(check_types.State.CRIT, states(total))
        self.assertAlmostEqual(metrics(total)['faz_log_gb_day'], 3.15 * 1024**2 / 1e9)
        root = list(logvolume_checks.check_adom_logvolume('root', {}, data))
        self.assertEqual(metrics(root)['faz_log_gb_day'], 0)
        data['logvolume']['data']['root']['date'] = '2020-01-01'
        self.assertEqual(metrics(list(logvolume_checks.check_adom_logvolume('root', {}, data))), {})
        self.assertIn(check_types.State.UNKNOWN, states(list(logvolume_checks.check_total_logvolume({}, data))))
        self.assertEqual(metrics(list(logvolume_checks.check_total_logvolume({}, {'logvolume': {'error': 'SSH failed'}}))), {})
        self.assertEqual(list(logvolume_checks.discover_total_logvolume({})), [])

    def test_password_transport_verifies_host_and_closes_connection(self):
        """
        Verify password transport verifies host and closes connection.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        import paramiko
        from unittest.mock import MagicMock
        channel = MagicMock()
        channel.recv_ready.side_effect = [True, False]
        channel.recv.return_value = self.fixture().encode()
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready.return_value = True
        channel.recv_exit_status.return_value = 0
        client = MagicMock()
        client.exec_command.return_value = (MagicMock(), types.SimpleNamespace(channel=channel), MagicMock())
        with patch.object(paramiko, 'SSHClient', return_value=client):
            result = agent.collect_logvolume_password('faz.example', 'admin', 'test-secret', known_hosts='/site/hosts', verify_host_key=True)
        self.assertIn('root', result['data'])
        client.load_host_keys.assert_called_once_with('/site/hosts')
        self.assertIsInstance(client.set_missing_host_key_policy.call_args.args[0], paramiko.RejectPolicy)
        self.assertEqual(client.connect.call_args.kwargs['password'], 'test-secret')
        self.assertFalse(client.connect.call_args.kwargs['allow_agent'])
        self.assertFalse(client.connect.call_args.kwargs['look_for_keys'])
        self.assertEqual(client.exec_command.call_args.args, ('diagnose fortilogd logvol-adom all',))
        client.close.assert_called_once()
        self.assertNotIn('test-secret', json.dumps(result))
        for failure in (paramiko.AuthenticationException('secret'), paramiko.SSHException('secret'), socket.timeout()):
            client.reset_mock()
            client.connect.side_effect = failure
            with patch.object(paramiko, 'SSHClient', return_value=client):
                result = agent.collect_logvolume_password('faz.example', 'admin', 'test-secret')
            self.assertIn('error', result)
            self.assertNotIn('secret', result['error'])
            client.close.assert_called_once()

    def test_password_transport_skips_host_keys_by_default_even_with_old_file(self):
        """
        Verify password transport skips host keys by default even with old file.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        import paramiko
        from unittest.mock import MagicMock
        client = MagicMock()
        channel = MagicMock()
        channel.recv_ready.side_effect = [True, False]
        channel.recv.return_value = self.fixture().encode()
        channel.recv_stderr_ready.return_value = False
        channel.exit_status_ready.return_value = True
        channel.recv_exit_status.return_value = 0
        client.exec_command.return_value = (MagicMock(), types.SimpleNamespace(channel=channel), MagicMock())
        with patch.object(paramiko, 'SSHClient', return_value=client):
            result = agent.collect_logvolume_password('faz.example', 'admin', 'test-secret', known_hosts='/old/known_hosts')
        self.assertIn('root', result['data'])
        client.load_host_keys.assert_not_called()
        client.load_system_host_keys.assert_not_called()
        client.save_host_keys.assert_not_called()
        self.assertIsInstance(client.set_missing_host_key_policy.call_args.args[0], paramiko.AutoAddPolicy)
        client.close.assert_called_once()

    def test_only_combined_services_discovered_with_multiple_graphs(self):
        """
        Verify only combined services discovered with multiple graphs.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        section = {'adoms': {'data': {'root': {'logs_per_second': 17.7, 'devices': 9, 'vdoms': 11}}},
                   'logvolume': {'data': {'root': {
                       'date': datetime.now(timezone.utc).date().isoformat(),
                       'gb_day': 0.301, 'average_gb_day': 0.334}}}}
        self.assertEqual([s.item for s in adoms_checks.discover_adoms(section)], ['root'])
        self.assertEqual(list(logvolume_checks.discover_logvolume(section)), [])
        self.assertEqual(list(logvolume_checks.discover_total_logvolume(section)), [])
        for result in (list(adoms_checks.check_adoms('root', NO_LEVELS, section)),
                       list(adoms_checks.check_total(NO_LEVELS, section))):
            emitted = metrics(result)
            self.assertEqual(emitted['logs_per_second'], 17.7)
            self.assertEqual(emitted['faz_log_gb_day'], 0.301)
            self.assertEqual(emitted['faz_log_average_gb_day'], 0.334)
            graphs = GraphTests().graphs()
            eligible = [g for g in graphs.values()
                        if not g['conflicting'] & emitted.keys()
                        and (g['simple_lines'] | g['compound_lines']) - g['optional'] <= emitted.keys()]
            covered = set().union(*(g['simple_lines'] for g in eligible))
            self.assertTrue({'logs_per_second', 'faz_log_gb_day', 'faz_log_average_gb_day'} <= covered)
            self.assertGreaterEqual(len(eligible), 3)

    def test_interactive_fortianalyzer_fallback_after_empty_exec(self):
        """
        Verify interactive FortiAnalyzer fallback after empty exec.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        import paramiko
        from unittest.mock import MagicMock
        client = MagicMock()
        exec_channel = MagicMock()
        exec_channel.recv_ready.return_value = False
        exec_channel.recv_stderr_ready.return_value = False
        exec_channel.exit_status_ready.return_value = True
        exec_channel.recv_exit_status.return_value = 0
        client.exec_command.return_value = (MagicMock(), types.SimpleNamespace(channel=exec_channel), MagicMock())
        shell = MagicMock()
        shell.recv_ready.return_value = True
        shell.recv.side_effect = [b'Welcome\r\nCH-FAZ-001 # ',
            ('diagnose fortilogd logvol-adom all\r\n' + self.fixture() + '\r\nCH-FAZ-001 # ').encode()]
        client.invoke_shell.return_value = shell
        with patch.object(paramiko, 'SSHClient', return_value=client):
            result = agent.collect_logvolume_password('faz.example', 'admin', 'test-secret')
        self.assertIn('root', result['data'])
        client.exec_command.assert_called_once_with('diagnose fortilogd logvol-adom all', timeout=30, get_pty=True)
        shell.sendall.assert_called_once_with('diagnose fortilogd logvol-adom all\n')
        shell.close.assert_called_once()
        client.close.assert_called_once()

    def test_real_seven_day_cli_layout_and_terminal_sequences(self):
        """
        Verify real seven day cli layout and terminal sequences.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        text = ("CH-FAZ-001 # diagnose fortilogd logvol-adom all\r\n"
                "\x1b[0m2026-10-11 2026-10-10 2026-10-09 2026-10-08 2026-10-07 2026-10-06 2026-10-05    average\r\n"
                "adom 'root':\r\n"
                " 279.27 MB 273.38 MB 332.40 MB 339.83 MB 415.65 MB 324.53 MB 255.56 MB 317.23 MB\r\n"
                "adom 'FortiAnalyzer':\r\n"
                " 0 B 0 B 0 B 0 B 0 B 0 B 0 B 0 B\r\nCH-FAZ-001 # ")
        rows = agent.parse_logvolume(text)
        self.assertEqual(len(rows['root']['history']), 7)
        self.assertAlmostEqual(rows['root']['gb_day'], 279.27 * 1024**2 / 1e9)
        self.assertEqual(rows['FortiAnalyzer']['gb_day'], 0)

    def test_interactive_parse_errors_are_specific_and_not_raw_remote_text(self):
        """
        Verify interactive parse errors are specific and not raw remote text.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        import paramiko
        from unittest.mock import MagicMock
        client = MagicMock()
        client.exec_command.side_effect = paramiko.SSHException('unsupported exec')
        shell = MagicMock()
        shell.recv_ready.return_value = True
        shell.recv.side_effect = [b'FAZ # ', b'Permission denied sensitive-text\nFAZ # ']
        client.invoke_shell.return_value = shell
        with patch.object(paramiko, 'SSHClient', return_value=client):
            result = agent.collect_logvolume_password('faz.example', 'admin', 'test-secret')
        self.assertIn('Missing or incomplete', result['error'])
        self.assertNotIn('sensitive', result['error'])
        client.close.assert_called_once()
        shell.close.assert_called_once()

    def test_password_reference_preserves_colons_and_does_not_leak_errors(self):
        """
        Verify password reference preserves colons and does not leak errors.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        api = types.ModuleType('cmk.utils.password_store')
        from unittest.mock import MagicMock
        api.lookup = MagicMock(return_value='test-secret')
        with patch.dict(sys.modules, {'cmk.utils.password_store': api}):
            self.assertEqual(agent.password_from_reference('store:entry:/site/passwords'), 'test-secret')
            api.lookup.assert_called_once_with(Path('/site/passwords'), 'store:entry')
            api.lookup.side_effect = ValueError('sensitive details')
            with self.assertRaises(agent.PasswordReferenceError) as error:
                agent.password_from_reference('entry:/site/passwords')
            self.assertNotIn('sensitive', str(error.exception))
            with self.assertRaises(agent.PasswordReferenceError):
                agent.password_from_reference('invalid')

    def test_missing_vdom_rates_are_informational_and_thresholds_still_apply(self):
        """
        Verify missing vdom rates are informational and thresholds still apply.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        data = {'adoms': {'data': {'root': {'logs_per_second': 27.6, 'devices': 9, 'vdoms': 11, 'missing_vdoms': 3}}}}
        for check in (lambda params: adoms_checks.check_adoms('root', params, data),
                      lambda params: adoms_checks.check_total(params, data)):
            for upper, expected in ((('no_levels', None), check_types.State.OK),
                                    (('fixed', (20, 30)), check_types.State.WARN),
                                    (('fixed', (10, 20)), check_types.State.CRIT)):
                results = list(check(dict(NO_LEVELS, upper=upper)))
                self.assertIn(expected, states(results))
                self.assertEqual(metrics(results)['faz_reported_logs_per_second'], 27.6)
                self.assertTrue(any('3 of 11' in getattr(r, 'details', '') for r in results))
                if expected == check_types.State.OK:
                    self.assertEqual(set(states(results)), {check_types.State.OK})

    def test_partial_rate_uses_checkmk_state_ordering_and_preserves_critical(self):
        """
        Verify partial rate uses checkmk state ordering and preserves critical.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        with self.assertRaises(TypeError):
            max(check_types.State.OK, check_types.State.WARN)
        params = {'upper': ('fixed', (10, 20)), 'lower': ('no_levels', None)}
        values = list(adoms_checks.check_lograte(params, 30, 'faz_reported_logs_per_second', 3, 11))
        self.assertIn(check_types.State.CRIT, states(values))
        self.assertEqual(metrics(values)['faz_reported_logs_per_second'], 30)

    def test_cli_volume_is_in_existing_rate_services_and_total(self):
        """
        Verify cli volume is in existing rate services and total.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        day = datetime.now(timezone.utc).date().isoformat()
        cli = (f'{day} 2026-07-20 average\n'
               "adom 'root':\n279.27 MB 273.38 MB 317.23 MB\n"
               "adom 'test':\n0 B 0 B 0 B\n")
        section = {'adoms': {'data': {
            'root': {'logs_per_second': 14.9, 'devices': 9, 'vdoms': 11, 'missing_vdoms': 3},
            'test': {'logs_per_second': 0, 'devices': 0, 'vdoms': 0}}},
            'logvolume': {'data': agent.parse_logvolume(cli)}}
        root = list(adoms_checks.check_adoms('root', NO_LEVELS, section))
        self.assertAlmostEqual(metrics(root)['faz_log_gb_day'], 279.27 * 1024**2 / 1e9)
        self.assertAlmostEqual(metrics(root)['faz_log_average_gb_day'], 317.23 * 1024**2 / 1e9)
        self.assertEqual(metrics(root)['faz_reported_logs_per_second'], 14.9)
        self.assertEqual(set(states(root)), {check_types.State.OK})
        total = list(adoms_checks.check_total(NO_LEVELS, section))
        self.assertAlmostEqual(metrics(total)['faz_log_gb_day'], metrics(root)['faz_log_gb_day'])
        self.assertEqual(metrics(total)['faz_reported_logs_per_second'], 14.9)
        self.assertEqual(metrics(list(adoms_checks.check_adoms('test', NO_LEVELS, section)))['faz_log_gb_day'], 0)
        params = dict(NO_LEVELS, volume_levels=('fixed', (0.1, 0.2)))
        self.assertIn(check_types.State.CRIT, states(list(adoms_checks.check_total(params, section))))
        section['logvolume'] = {'error': 'SSH failed'}
        failed = list(adoms_checks.check_adoms('root', NO_LEVELS, section))
        self.assertIn(check_types.State.UNKNOWN, states(failed))
        self.assertNotIn('faz_log_gb_day', metrics(failed))
        self.assertEqual(metrics(failed)['faz_reported_logs_per_second'], 14.9)

    def test_ssh_volume_uses_only_api_credentials_ignoring_old_overrides(self):
        """
        Verify ssh volume uses only API credentials ignoring old overrides.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        with patch.object(agent, 'Client', return_value=FakeClient()), \
                patch.object(agent, 'collect_logvolume_password', return_value={'data': {}}) as ssh, \
                patch.object(agent.sys, 'stdin', io.StringIO('api-secret\n')), \
                patch('sys.stdout', io.StringIO()):
            self.assertEqual(agent.main(['--address', 'faz.example', '--user', 'api-user', '--password-stdin',
                '--ssh-logvolume', '--ssh-user', 'old-user', '--ssh-password-id', 'invalid-legacy-reference',
                '--ssh-address', 'old.example', '--ssh-known-hosts', '/old/path', '--ssh-verify-host-key']), 0)
        self.assertEqual(ssh.call_args.args[:3], ('faz.example', 'api-user', 'api-secret'))
        self.assertFalse(ssh.call_args.kwargs['verify_host_key'])
        self.assertNotIn('known_hosts', ssh.call_args.kwargs)

    def test_main_password_login_uses_api_password_by_default(self):
        """
        Verify main password login uses API password by default.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        with patch.object(agent, 'Client', return_value=FakeClient()), \
                patch.object(agent, 'collect_logvolume_password', return_value={'data': {}}) as ssh, \
                patch.object(agent.sys, 'stdin', io.StringIO('test-password\n')), \
                patch('sys.stdout', io.StringIO()):
            self.assertEqual(agent.main(['--address', 'faz.example', '--user', 'api-user', '--password-stdin',
                                         '--ssh-user', 'admin']), 0)
        self.assertEqual(ssh.call_args.args[:3], ('faz.example', 'api-user', 'test-password'))

    def test_ssh_failures_are_classified_without_raw_output(self):
        """
        Verify ssh failures are classified without raw output.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        for stderr, expected in (
            ('Host key verification failed.', 'Host key missing'),
            ('WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!', 'Host key changed'),
            ('Permission denied (publickey,password).', 'authentication rejected'),
            ('Connection refused', 'connection refused'),
            ('WARNING: UNPROTECTED PRIVATE KEY FILE!', 'permissions too open'),
            ('Could not resolve hostname secret-host', 'cannot be resolved'),
            ('No matching key exchange method found', 'negotiation failed'),
            ('arbitrary sensitive server response', 'exit 255')):
            with self.subTest(stderr=stderr), patch.object(agent.subprocess, 'run',
                    return_value=types.SimpleNamespace(returncode=255, stderr=stderr, stdout='')):
                error = agent.collect_logvolume('faz.example', 'monitor', '/site/key')['error']
                self.assertIn(expected, error)
                self.assertNotIn('secret-host', error)
                self.assertNotIn('sensitive', error)

    def test_main_emits_ssh_section_with_api_data(self):
        """
        Verify main emits ssh section with API data.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        output = io.StringIO()
        with patch.object(agent, 'Client', return_value=FakeClient()), \
                patch.object(agent, 'collect_logvolume_password', return_value={'error': 'SSH failed'}) as ssh, \
                patch.object(agent.sys, 'stdin', io.StringIO('test-password\n')), \
                patch('sys.stdout', output):
            self.assertEqual(agent.main(['--address', 'faz.example', '--user', 'api-user', '--password-stdin',
                                         '--ssh-user', 'ssh-user', '--ssh-identity-file', '/site/key']), 0)
        section = json.loads(output.getvalue().splitlines()[1])
        self.assertEqual(section['logvolume']['error'], 'SSH failed')
        self.assertEqual(section['api']['errors'], [])
        self.assertIn('system', section)
        self.assertEqual(ssh.call_args.args[:3], ('faz.example', 'api-user', 'test-password'))

    def test_partial_lograte_has_one_rate_summary_and_coverage_details(self):
        """
        Verify partial log rate has one rate summary and coverage details.

        Input:
            Test fixtures and mocks defined by this test case.

        Output:
            None; assertions fail if the expected behavior is not met.

        """
        section = {'adoms': {'data': {'root': {'logs_per_second': 14.9, 'devices': 9, 'vdoms': 11, 'missing_vdoms': 3}}}}
        results = list(adoms_checks.check_adoms('root', NO_LEVELS, section))
        summaries = [r.summary for r in results if isinstance(r, check_types.Result)]
        self.assertEqual(sum('logs/s' in text for text in summaries), 1)
        self.assertEqual(set(states(results)), {check_types.State.OK})
        self.assertTrue(any('3 of 11' in getattr(r, 'details', '') for r in results))
        total = list(adoms_checks.check_total(NO_LEVELS, section))
        self.assertEqual(metrics(total)['faz_reported_logs_per_second'], 14.9)
        self.assertEqual(set(states(total)), {check_types.State.OK})


class AuthenticationTests(unittest.TestCase):
    """
    Authentication migration, request lifecycle and safe secret transport.
    """

    def migrate(self, value):
        tree = ast.parse((FAMILY / 'rulesets/special_agent.py').read_text())
        namespace = {}
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name.startswith('migrate_')]
        exec(compile(ast.Module(body=functions, type_ignores=[]),
                     '<authentication migration>', 'exec'), namespace)
        return namespace['migrate_password_fields'](value)

    def test_migration_preserves_credentials_method_and_options(self):
        secret = ('cmk_postprocessed', 'stored_password', ('uuid', 'entry'))
        for method, explicit in (('password', False), ('password', True), ('token', True)):
            with self.subTest(method=method, explicit=explicit):
                old = {'user': 'monitor', 'password': secret, 'port': 8443,
                       'exclude_adoms': [], 'ssh_logvolume': {'port': 2222}}
                if explicit:
                    old['auth_method'] = method
                snapshot = copy.deepcopy(old)
                migrated = self.migrate(old)
                credentials = secret if method == 'token' else {'user': 'monitor', 'password': secret}
                self.assertEqual(migrated['authentication'], (method, credentials))
                for key in ('port', 'exclude_adoms', 'ssh_logvolume'):
                    self.assertEqual(migrated[key], old[key])
                self.assertFalse({'user', 'password', 'auth_method'} & migrated.keys())
                self.assertEqual(old, snapshot)
                self.assertEqual(self.migrate(migrated), migrated)

    def test_nested_credentials_are_preserved(self):
        for auth in (('password', {'user': 'monitor', 'password': ('store', 'entry')}),
                     ('token', ('store', 'token'))):
            rule = {'authentication': auth, 'exclude_adoms': ['custom']}
            self.assertEqual(self.migrate(rule), rule)
        self.assertIsNone(self.migrate(None))

    class Secret:
        def __str__(self):
            raise AssertionError('Secret must not be expanded into argv')

    def command_args(self, params):
        api = types.ModuleType('cmk.server_side_calls.v1')
        api.Secret = self.Secret
        api.SpecialAgentCommand = lambda **kwargs: types.SimpleNamespace(**kwargs)
        api.SpecialAgentConfig = lambda **kwargs: types.SimpleNamespace(**kwargs)
        api.noop_parser = lambda value: value
        with patch.dict(sys.modules, {'cmk.server_side_calls.v1': api}):
            module = load('faz_auth_commands', FAMILY / 'server_side_calls/fortianalyzer.py')
        host = types.SimpleNamespace(name='faz.example',
                                    primary_ip_config=types.SimpleNamespace(address='192.0.2.10'))
        command, = module.commands(params, host)
        return command.command_arguments

    def test_both_methods_forward_secret_objects_without_expansion(self):
        secret = self.Secret()
        for nested in (False, True):
            for method in ('password', 'token'):
                with self.subTest(nested=nested, method=method):
                    credentials = secret if method == 'token' else {'user': 'monitor', 'password': secret}
                    params = {'authentication': (method, credentials)} if nested else {
                        'auth_method': method, 'user': 'monitor', 'password': secret}
                    args = self.command_args(params)
                    flag = '--api-token-id' if method == 'token' else '--password-id'
                    self.assertIs(args[args.index(flag) + 1], secret)
                    if method == 'token':
                        self.assertNotIn('--user', args)
                        self.assertNotIn('--password-id', args)
                    else:
                        self.assertIn('monitor', args)
                        self.assertNotIn('--api-token-id', args)

    def test_plaintext_secrets_and_invalid_methods_are_rejected(self):
        for method in ('password', 'token'):
            credentials = 'plaintext' if method == 'token' else {'user': 'u', 'password': 'plaintext'}
            with self.subTest(method=method), self.assertRaises(TypeError):
                self.command_args({'authentication': (method, credentials)})
        with self.assertRaises(ValueError):
            self.command_args({'authentication': ('unknown', self.Secret())})
        with self.assertRaises(ValueError):
            self.command_args({'authentication': ('password', {'user': '', 'password': self.Secret()})})

    def test_bearer_header_on_jsonrpc_and_gui_without_session(self):
        transport = TransportTests()
        client = transport.client({'result': [{'status': {'code': 0}, 'data': {}}]})
        client.api_token = 'test-token'
        client.login(None, None)
        self.assertEqual(transport.requests, [])
        client.session = 'old-session'
        for url, gui in (('/sys/status', False), ('/gui/sys/license', True)):
            client.call(url, gui=gui)
            request = transport.requests[-1]
            self.assertEqual(request.get_header('Authorization'), 'Bearer test-token')
            self.assertIsNone(request.get_header('Cookie'))
            self.assertNotIn('session', json.loads(request.data))
            self.assertNotIn('test-token', request.data.decode())
        client.logout()
        self.assertEqual(len(transport.requests), 2)
        self.assertIsNone(client.session)

    def test_invalid_tokens_are_rejected_without_echoing_secret(self):
        for token in ('', 'secret\r\nInjected: header', 'secret space', 'secret\x00', 'sëcret'):
            with self.subTest(token=repr(token)), self.assertRaises(agent.APIError) as error:
                agent.Client('faz.example', api_token=token)
            self.assertEqual(str(error.exception), 'Invalid API token')

    def test_token_collector_skips_gui_login_logout_and_preserves_partial_failures(self):
        from unittest.mock import Mock
        client = FakeClient({'/gui/sys/license': 'HTTP 400',
                             '/gui/sys/resource/realtime': 'HTTP 400',
                             '/logview/adom/empty/logstats': 'Timeout'})
        client.api_token = 'test-token'
        client.login = Mock(side_effect=AssertionError('unexpected login'))
        client.logout = Mock(side_effect=AssertionError('unexpected logout'))
        data = agent.collect(client, None, None)
        client.login.assert_not_called()
        client.logout.assert_not_called()
        self.assertIn('system', data)
        self.assertNotIn('license', data)
        self.assertNotIn('resources', data)
        self.assertFalse(any(url.startswith('/gui/') for url, _ in client.calls))
        self.assertEqual(data['api']['errors'], ['ADOM empty: Timeout'])
        self.assertIn('error', data['adoms']['data']['empty'])
        self.assertIn('logs_per_second', data['adoms']['data']['production / 7.4'])

    def test_main_resolves_both_reference_types_in_process(self):
        for method, flag in (('password', '--password-id'), ('token', '--api-token-id')):
            with self.subTest(method=method):
                client = FakeClient()
                client.api_token = 'resolved-secret' if method == 'token' else None
                argv = ['--address', 'faz.example', flag, 'store:entry:/site/passwords']
                if method == 'password':
                    argv += ['--user', 'monitor']
                output = io.StringIO()
                with patch.object(agent, 'password_from_reference', return_value='resolved-secret') as lookup, \
                        patch.object(agent, 'Client', return_value=client) as factory, \
                        patch('sys.stdout', output):
                    self.assertEqual(agent.main(argv), 0)
                lookup.assert_called_once_with('store:entry:/site/passwords')
                self.assertEqual(factory.call_args.kwargs['api_token'], client.api_token)
                self.assertNotIn('resolved-secret', output.getvalue())

    def test_token_with_ssh_silently_skips_collection(self):
        client = FakeClient()
        client.api_token = 'test-token'
        output = io.StringIO()
        with patch.object(agent, 'Client', return_value=client), \
                patch.object(agent, 'collect_logvolume_password') as ssh, \
                patch('sys.stdin', io.StringIO('test-token\n')), patch('sys.stdout', output):
            self.assertEqual(agent.main(['--address', 'faz.example', '--api-token-stdin', '--ssh-logvolume']), 0)
        ssh.assert_not_called()
        data = json.loads(output.getvalue().splitlines()[1])
        self.assertNotIn('logvolume', data)
        self.assertEqual(data['api']['errors'], [])
        self.assertNotIn('test-token', output.getvalue())

    def test_gui_services_are_not_discovered_for_token_authentication(self):
        client = FakeClient()
        client.api_token = 'test-token'
        data = agent.collect(client, None, None)
        for module, name in ((license_checks, 'check_plugin_fortianalyzer_license'),
                             (managed_checks, 'check_plugin_fortianalyzer_managed'),
                             (support_checks, 'check_plugin_fortianalyzer_support'),
                             (resources_checks, 'check_plugin_fortianalyzer_resources_combined')):
            with self.subTest(plugin=name):
                discover = getattr(module, name).discovery_function
                self.assertEqual(list(discover(data)), [])
                self.assertEqual(len(list(discover(section()))), 1)
                # Admin query errors must still be discovered and reported.
                self.assertEqual(len(list(discover({'authentication': 'password',
                    'license': {'error': 'HTTP 400'}, 'resources': {'error': 'HTTP 400'}}))), 1)
        self.assertEqual(len(list(api_checks.check_plugin_fortianalyzer_api.discovery_function(data))), 1)
        self.assertEqual(states(list(api_checks.check_api(data))), [check_types.State.OK])
        self.assertTrue(list(adoms_checks.discover_adoms(data)))

    def test_token_commands_ignore_saved_ssh_settings(self):
        args = self.command_args({'authentication': ('token', self.Secret()),
                                  'ssh_logvolume': {'port': 2222}})
        self.assertNotIn('--ssh-logvolume', args)
        self.assertNotIn('--ssh-port', args)

    def test_cli_rejects_missing_or_conflicting_credentials(self):
        for options in ([], ['--password-stdin'], ['--password-id', 'ref', '--api-token-id', 'other']):
            with self.subTest(options=options), patch('sys.stderr', io.StringIO()), \
                    self.assertRaises(SystemExit):
                agent.main(['--address', 'faz.example'] + options)

    def test_reference_failure_never_leaks_secret_or_reference(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(agent, 'password_from_reference', side_effect=ValueError('sensitive')), \
                patch('sys.stdout', output), patch('sys.stderr', errors):
            self.assertEqual(agent.main(['--address', 'faz.example', '--api-token-id', 'private-reference']), 1)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('sensitive', errors.getvalue())
        self.assertNotIn('private-reference', errors.getvalue())


if __name__ == '__main__':
    unittest.main()

