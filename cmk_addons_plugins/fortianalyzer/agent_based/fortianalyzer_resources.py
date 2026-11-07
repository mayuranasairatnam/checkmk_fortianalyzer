"""
FortiAnalyzer: CPU, memory and disk resource checks.
"""

import math

from cmk.agent_based.v2 import CheckPlugin, Metric, Result, State, check_levels, render

from ..lib.common import discover_gui_single, number, source


RESOURCE_PERCENTAGES = {
    'CPU Average': ('cpu_avg', 'faz_cpu_percent', 'cpu'),
    'Disk Usage': ('disk', 'faz_disk_percent', 'disk'),
    'Memory Usage': ('memory', 'faz_memory_percent', 'memory'),
}


RESOURCE_MEMORY = {
    'Memory Used': 'faz_memory_used',
    'Memory Total': 'faz_memory_total',
    'Memory Free': 'faz_memory_free',
}


def discover_resources(section):
    """
    Discover services for resources.

    Input:
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Service objects according to the discovery conditions.

    """
    yield from discover_gui_single(section)


def discover_retired_resources(section):
    """
    Keep the retired discovery callback available for existing registrations.

    Input:
        section: Parsed agent data for the registered section.

    Output:
        Yields no services; replacement services are discovered by the active callbacks.

    """
    yield from ()


def check_resources(item, params, section):
    """
    Evaluate resources and report monitoring results.

    Input:
        item: Service item identifying the monitored entity.
        params: Checkmk rule parameters, including the configured thresholds.
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    if item not in RESOURCE_PERCENTAGES and item not in RESOURCE_MEMORY:
        yield Result(state=State.UNKNOWN, summary='Resources service replaced by dedicated sensors; run service discovery')
        return
    data, error = source(section, 'resources')
    if error:
        yield Result(state=State.UNKNOWN, summary=error)
        return
    if item in RESOURCE_PERCENTAGES:
        field, metric, levels = RESOURCE_PERCENTAGES[item]
        value = number(data.get(field))
        if value is None or not 0 <= value <= 100:
            yield Result(state=State.UNKNOWN, summary='Missing or invalid percentage: ' + field)
        else:
            yield from check_levels(value, levels_upper=params[levels], metric_name=metric,
                                    label='', render_func=render.percent, boundaries=(0, 100))
        return
    used, total = number(data.get('memory_used')), number(data.get('memory_total'))
    if total is None or total <= 0 or (item != 'Memory Total' and (used is None or not 0 <= used <= total)):
        yield Result(state=State.UNKNOWN, summary='Missing or invalid memory_used / memory_total')
        return
    factor = {'bytes': 1, 'kib': 1024, 'mib': 1024 ** 2, 'gb': 1000 ** 3, 'gib': 1024 ** 3}[params['memory_unit']]
    value = (total if item == 'Memory Total' else used if item == 'Memory Used' else total - used) * factor
    total_bytes = total * factor
    if not math.isfinite(value) or not math.isfinite(total_bytes):
        yield Result(state=State.UNKNOWN, summary='Invalid converted memory size')
        return
    yield Result(state=State.OK, summary=f'{value / 1e9:.3f} GB')
    yield Metric(RESOURCE_MEMORY[item], value, boundaries=(0, total_bytes))


def check_combined_resources(params, section):
    """
    Evaluate combined resources and report monitoring results.

    Input:
        params: Checkmk rule parameters, including the configured thresholds.
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    data, error = source(section, 'resources')
    if error:
        yield Result(state=State.UNKNOWN, summary=error)
        return
    for field, metric, levels, label in (
        ('cpu_avg', 'faz_cpu_percent', 'cpu', 'CPU average'),
        ('disk', 'faz_disk_percent', 'disk', 'Disk usage'),
        ('memory', 'faz_memory_percent', 'memory', 'Memory usage'),
    ):
        value = number(data.get(field))
        if value is None or not 0 <= value <= 100:
            yield Result(state=State.UNKNOWN, summary=label + ': missing or invalid percentage')
        else:
            yield from check_levels(value, levels_upper=params[levels], metric_name=metric,
                                    label=label, render_func=render.percent, boundaries=(0, 100))
    used, total = number(data.get('memory_used')), number(data.get('memory_total'))
    if total is None or total <= 0:
        yield Result(state=State.UNKNOWN, summary='Missing or invalid memory_total')
        return
    factor = {'bytes': 1, 'kib': 1024, 'mib': 1024 ** 2, 'gb': 1000 ** 3, 'gib': 1024 ** 3}[params['memory_unit']]
    total_bytes = total * factor
    if not math.isfinite(total_bytes):
        yield Result(state=State.UNKNOWN, summary='Invalid converted memory total')
        return
    yield Metric('faz_memory_total', total_bytes, boundaries=(0, total_bytes))
    if used is None or not 0 <= used <= total:
        yield Result(state=State.OK, summary='Memory total: ' + render.bytes(total_bytes))
        yield Result(state=State.UNKNOWN, summary='Missing or invalid memory_used')
        return
    used_bytes = used * factor
    free_bytes = total_bytes - used_bytes
    yield Result(state=State.OK, summary=f'Memory: {render.bytes(used_bytes)} of {render.bytes(total_bytes)} used, {render.bytes(free_bytes)} free')
    yield Metric('faz_memory_used', used_bytes, boundaries=(0, total_bytes))
    yield Metric('faz_memory_free', free_bytes, boundaries=(0, total_bytes))


check_plugin_fortianalyzer_resources = CheckPlugin(
    name='fortianalyzer_resources', sections=['fortianalyzer'], service_name='FortiAnalyzer Resources %s',
    discovery_function=discover_retired_resources, check_function=check_resources,
    check_ruleset_name='fortianalyzer_resources', check_default_parameters={
        'cpu': ('fixed', (80.0, 90.0)), 'memory': ('fixed', (80.0, 90.0)),
        'disk': ('fixed', (80.0, 90.0)), 'memory_unit': 'kib'})


check_plugin_fortianalyzer_resources_combined = CheckPlugin(
    name='fortianalyzer_resources_combined', sections=['fortianalyzer'], service_name='FortiAnalyzer Resources',
    discovery_function=discover_resources, check_function=check_combined_resources,
    check_ruleset_name='fortianalyzer_resources', check_default_parameters={
        'cpu': ('fixed', (80.0, 90.0)), 'memory': ('fixed', (80.0, 90.0)),
        'disk': ('fixed', (80.0, 90.0)), 'memory_unit': 'kib'})
