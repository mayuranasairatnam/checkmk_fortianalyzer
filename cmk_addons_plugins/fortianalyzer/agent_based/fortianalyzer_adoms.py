"""
FortiAnalyzer: ADOM discovery and monitoring checks.
"""

import math

from cmk.agent_based.v2 import CheckPlugin, Metric, Result, Service, State, check_levels

from ..lib.common import count, discover_single, number, source
from .fortianalyzer_logvolume import check_logvolume


def discover_adoms(section):
    """
    Discover services for ADOMs.

    Input:
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Service objects according to the discovery conditions.

    """
    data, error = source(section, 'adoms')
    if not error:
        for name in sorted(data):
            yield Service(item=name)


def log_values(entry):
    """
    Validate normalized ADOM log statistics.

    Input:
        entry: API record containing the relevant fields.

    Output:
        (logs_per_second, devices, vdoms), or None for invalid statistics.

    """
    if not isinstance(entry, dict) or entry.get('error'):
        return None
    rate = number(entry.get('logs_per_second'))
    devices, vdoms = count(entry.get('devices')), count(entry.get('vdoms'))
    if rate is None or rate < 0 or devices is None or vdoms is None:
        return None
    missing = count(entry.get('missing_vdoms', 0))
    if missing is None or missing > vdoms:
        return None
    return rate, devices, vdoms


def check_adom_rates(item, params, section):
    """
    Evaluate ADOM rates and report monitoring results.

    Input:
        item: Service item identifying the monitored entity.
        params: Checkmk rule parameters, including the configured thresholds.
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    data, error = source(section, 'adoms')
    if error:
        yield Result(state=State.UNKNOWN, summary=error)
        return
    entry = data.get(item)
    if not isinstance(entry, dict):
        yield Result(state=State.UNKNOWN, summary='ADOM no longer returned by API; run service discovery')
        return
    if entry.get('error'):
        yield Result(state=State.UNKNOWN, summary=str(entry['error']))
        return
    values = log_values(entry)
    if values is None:
        yield Result(state=State.UNKNOWN, summary='Missing or invalid ADOM log statistics')
        return
    rate, devices, vdoms = values
    yield Result(state=State.OK, summary=f'Devices: {devices:.0f}, VDOMs: {vdoms:.0f}')
    yield Metric('devices', devices)
    yield Metric('vdoms', vdoms)
    missing = entry.get('missing_vdoms', 0)
    if missing:
        if missing == vdoms:
            yield Result(state=State.UNKNOWN, summary=f'No log rates reported for {missing} VDOMs')
        else:
            yield from check_lograte(params, rate, 'faz_reported_logs_per_second', missing, vdoms)
        return
    yield from check_lograte(params, rate)


def check_lograte(params, rate, metric='logs_per_second', missing=0, vdoms=0):
    """
    Evaluate log rate and report monitoring results.

    Input:
        params: Checkmk rule parameters, including the configured thresholds.
        rate: Reported log rate in logs per second.
        metric: Name of the emitted rate metric.
        missing: Number of VDOMs without a reported log rate.
        vdoms: Total number of VDOMs in the rate scope.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    for result in check_levels(rate, levels_upper=params.get('upper'), levels_lower=params.get('lower'),
                               metric_name=metric, label='Log rate',
                               render_func=lambda value: f'{value:.2f} logs/s', boundaries=(0, None)):
        if missing and isinstance(result, Result):
            yield Result(state=result.state, summary=result.summary,
                         details=f'Rate coverage: {missing} of {vdoms:.0f} VDOMs without lograte. The displayed value is the sum of reported rates.')
        else:
            yield result


def check_total_rates(params, section):
    """
    Evaluate total rates and report monitoring results.

    Input:
        params: Checkmk rule parameters, including the configured thresholds.
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    data, error = source(section, 'adoms')
    if error:
        yield Result(state=State.UNKNOWN, summary=error)
        return
    values = [log_values(entry) for entry in data.values()]
    failed = [name for name, entry in data.items() if log_values(entry) is None]
    partial = [name for name, entry in data.items() if log_values(entry) is not None and entry.get('missing_vdoms', 0)]
    excluded = section.get('adoms', {}).get('excluded', [])
    if excluded:
        yield Result(state=State.OK, summary='Explicitly excluded ADOMs: ' + ', '.join(excluded))
    if failed:
        yield Result(state=State.UNKNOWN, summary='Total log rate incomplete; failed ADOMs: ' + ', '.join(sorted(failed)))
        return
    try:
        total = math.fsum(entry[0] for entry in values)
    except OverflowError:
        yield Result(state=State.UNKNOWN, summary='Total log rate overflow')
        return
    if not math.isfinite(total):
        yield Result(state=State.UNKNOWN, summary='Invalid total log rate')
        return
    yield Result(state=State.OK, summary=f'ADOMs: {len(data)}')
    if partial:
        reported = sum(entry['vdoms'] - entry.get('missing_vdoms', 0) for entry in data.values())
        if reported == 0:
            yield Result(state=State.UNKNOWN, summary='No VDOM log rates reported')
        else:
            vdoms = sum(entry['vdoms'] for entry in data.values())
            yield from check_lograte(params, total, 'faz_reported_logs_per_second', vdoms - reported, vdoms)
        return
    yield from check_lograte(params, total)


def check_adoms(item, params, section):
    """
    Evaluate ADOMs and report monitoring results.

    Input:
        item: Service item identifying the monitored entity.
        params: Checkmk rule parameters, including the configured thresholds.
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    yield from check_adom_rates(item, params, section)
    if 'logvolume' in section:
        yield from check_logvolume({'levels': params.get('volume_levels')}, section, item, show_scope=False)


def check_total(params, section):
    """
    Evaluate total and report monitoring results.

    Input:
        params: Checkmk rule parameters, including the configured thresholds.
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    yield from check_total_rates(params, section)
    if 'logvolume' in section:
        yield from check_logvolume({'levels': params.get('volume_levels')}, section, show_scope=False)


check_plugin_fortianalyzer_adoms = CheckPlugin(
    name='fortianalyzer_adoms', sections=['fortianalyzer'], service_name='FortiAnalyzer ADOM %s Log Metrics',
    discovery_function=discover_adoms, check_function=check_adoms,
    check_ruleset_name='fortianalyzer_adom_lograte', check_default_parameters={
        'upper': ('no_levels', None), 'lower': ('no_levels', None)})


check_plugin_fortianalyzer_total = CheckPlugin(
    name='fortianalyzer_total', sections=['fortianalyzer'], service_name='FortiAnalyzer Total Log Metrics',
    discovery_function=discover_single, check_function=check_total,
    check_ruleset_name='fortianalyzer_total_lograte', check_default_parameters={
        'upper': ('no_levels', None), 'lower': ('no_levels', None)})
