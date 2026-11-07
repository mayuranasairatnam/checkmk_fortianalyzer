"""
FortiAnalyzer: Device license capacity and utilization check.
"""

from cmk.agent_based.v2 import CheckPlugin, Metric, Result, State, check_levels, render

from ..lib.common import count, discover_gui_single, source


def check_license(params, section):
    """
    Evaluate license and report monitoring results.

    Input:
        params: Checkmk rule parameters, including the configured thresholds.
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    data, error = source(section, 'license')
    if error:
        yield Result(state=State.UNKNOWN, summary=error)
        return
    used, licensed = count(data.get('current_num_dev')), count(data.get('max_num_dev'))
    if used is None or licensed is None:
        yield Result(state=State.UNKNOWN, summary='Missing or invalid current_num_dev / max_num_dev')
        return
    free = licensed - used
    yield Result(state=State.OK, summary=f'Used: {used:.0f}, licensed: {licensed:.0f}, free: {free:.0f}')
    for name, value in (('used_devices', used), ('licensed_devices', licensed), ('free_devices', free)):
        yield Metric(name, value)
    if licensed == 0:
        yield Result(state=State.CRIT if used > 0 else State.UNKNOWN,
                     summary='Licensed capacity is zero; utilization cannot be calculated')
        return
    if used > licensed:
        yield Result(state=State.CRIT, summary='Licensed device capacity exceeded')
    yield from check_levels(used / licensed * 100, levels_upper=params['levels'],
                            metric_name='utilization_percent', label='License utilization',
                            render_func=render.percent, boundaries=(0, 100))


check_plugin_fortianalyzer_license = CheckPlugin(
    name='fortianalyzer_license', sections=['fortianalyzer'], service_name='FortiAnalyzer Device License',
    discovery_function=discover_gui_single, check_function=check_license,
    check_ruleset_name='fortianalyzer_license', check_default_parameters={'levels': ('fixed', (80.0, 90.0))})
