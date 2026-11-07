"""
FortiAnalyzer: SSH log-volume validation and checks.

Volume results are included in the ADOM and total log metrics services.
Legacy volume registrations remain available for existing services;
their discovery callbacks do not create additional services.
"""

from datetime import date, datetime, timezone
import json
import math

from cmk.agent_based.v2 import CheckPlugin, Metric, Result, State, check_levels

from ..lib.common import number, source


def discover_logvolume(section):
    """
    Keep the retired discovery callback available for existing registrations.

    Input:
        section: Parsed agent data for the registered section.

    Output:
        Yields no services; replacement services are discovered by the active callbacks.

    """
    # Legacy checks stay loadable until vanished services are removed.
    # Volume is now monitored in the existing ADOM Log Rate service.
    yield from ()


def discover_total_logvolume(section):
    """
    Keep the retired discovery callback available for existing registrations.

    Input:
        section: Parsed agent data for the registered section.

    Output:
        Yields no services; replacement services are discovered by the active callbacks.

    """
    yield from ()


def volume_rows(section, item=None):
    """
    Validate SSH volume rows and their shared reporting date.

    Input:
        section: Parsed agent data for the registered section.
        item: Service item identifying the monitored entity.

    Output:
        (entries, None) on success, or (None, error_message) on failure.

    """
    data, error = source(section, 'logvolume')
    if error:
        return None, error
    entries = [data.get(item)] if item is not None else list(data.values())
    dates = set()
    for entry in entries:
        if not isinstance(entry, dict):
            return None, 'ADOM no longer returned by SSH; run discovery'
        try:
            dates.add(date.fromisoformat(entry['date']))
        except (KeyError, TypeError, ValueError):
            return None, 'Missing or invalid log-volume date'
        for field in ('gb_day', 'average_gb_day'):
            value = number(entry.get(field))
            if value is None or value < 0:
                return None, 'Missing or invalid log volume'
    if len(dates) > 1:
        return None, 'Inconsistent log-volume dates'
    return entries, None


def check_logvolume(params, section, item=None, show_scope=True):
    """
    Evaluate log volume and report monitoring results.

    Input:
        params: Checkmk rule parameters, including the configured thresholds.
        section: Parsed agent data for the registered section.
        item: Service item identifying the monitored entity.
        show_scope: Whether to include ADOM scope information in the output.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    entries, error = volume_rows(section, item)
    if error:
        yield Result(state=State.UNKNOWN, summary=error)
        return
    try:
        daily = math.fsum(float(entry['gb_day']) for entry in entries)
        average = math.fsum(float(entry['average_gb_day']) for entry in entries)
    except OverflowError:
        yield Result(state=State.UNKNOWN, summary='Log-volume overflow')
        return
    if not math.isfinite(daily) or not math.isfinite(average):
        yield Result(state=State.UNKNOWN, summary='Invalid log-volume total')
        return
    excluded = section.get('logvolume', {}).get('excluded', [])
    if show_scope and item is None and excluded:
        yield Result(state=State.OK, summary='Excluded ADOMs: ' + ', '.join(excluded))
    if entries:
        day = date.fromisoformat(entries[0]['date'])
        age = (datetime.now(timezone.utc).date() - day).days
        yield Result(state=State.WARN if age > 2 or age < -1 else State.OK,
                     summary=f'Date: {day}', details='Daily volume is the counter for this calendar date, not an extrapolated rate. ' +
                     ('Stale or future CLI date. ' if age > 2 or age < -1 else '') +
                     json.dumps({str(index): entry.get('history', {}) for index, entry in enumerate(entries)}, sort_keys=True))
    else:
        yield Result(state=State.OK, summary='No ADOMs in configured monitoring scope')
    if entries and (age > 2 or age < -1):
        return  # Do not write a historical CLI counter as a current RRD sample.
    yield from check_levels(daily, levels_upper=params.get('levels'), metric_name='faz_log_gb_day',
                            label='Log volume', render_func=lambda value: f'{value:.3f} GB/day', boundaries=(0, None))
    yield Result(state=State.OK, summary=f'CLI average: {average:.3f} GB/day')
    yield Metric('faz_log_average_gb_day', average)


def check_total_logvolume(params, section):
    """
    Evaluate total log volume and report monitoring results.

    Input:
        params: Checkmk rule parameters, including the configured thresholds.
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    yield from check_logvolume(params, section)


def check_adom_logvolume(item, params, section):
    """
    Evaluate ADOM log volume and report monitoring results.

    Input:
        item: Service item identifying the monitored entity.
        params: Checkmk rule parameters, including the configured thresholds.
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Result objects and metrics produced by the check or its helpers.

    """
    yield from check_logvolume(params, section, item)


check_plugin_fortianalyzer_adom_logvolume = CheckPlugin(
    name='fortianalyzer_adom_logvolume', sections=['fortianalyzer'],
    service_name='FortiAnalyzer ADOM %s Log Volume', discovery_function=discover_logvolume,
    check_function=check_adom_logvolume, check_ruleset_name='fortianalyzer_adom_logvolume',
    check_default_parameters={'levels': ('no_levels', None)})


check_plugin_fortianalyzer_total_logvolume = CheckPlugin(
    name='fortianalyzer_total_logvolume', sections=['fortianalyzer'],
    service_name='FortiAnalyzer Total Log Volume', discovery_function=discover_total_logvolume,
    check_function=check_total_logvolume, check_ruleset_name='fortianalyzer_total_logvolume',
    check_default_parameters={'levels': ('no_levels', None)})
