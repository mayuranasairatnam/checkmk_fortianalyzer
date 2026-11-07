"""
FortiAnalyzer: Managed device count checks.
"""

from cmk.agent_based.v2 import CheckPlugin, Metric, Result, State

from ..lib.common import count, discover_gui_single, source


def check_managed(section):
    """
    Evaluate managed and report monitoring results.

    Input:
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    data, error = source(section, 'license')
    if error:
        yield Result(state=State.UNKNOWN, summary=error)
        return
    raw = data.get('dev_num_count')
    raw = raw if isinstance(raw, dict) else {}
    entry = raw.get('fgt_cnt')
    value = count(entry.get('val')) if isinstance(entry, dict) else None
    if value is None:
        yield Result(state=State.UNKNOWN, summary='FortiGates / Logging Devices: missing or invalid count')
    else:
        yield Result(state=State.OK, summary=f'FortiGates / Logging Devices: {value:.0f}')
        yield Metric('faz_logging_devices', value)


check_plugin_fortianalyzer_managed = CheckPlugin(
    name='fortianalyzer_managed', sections=['fortianalyzer'], service_name='FortiAnalyzer Managed Devices',
    discovery_function=discover_gui_single, check_function=check_managed)
