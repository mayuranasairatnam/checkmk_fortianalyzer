"""
FortiAnalyzer: Support license status and expiry check.
"""

from datetime import datetime, timezone
import re

from cmk.agent_based.v2 import CheckPlugin, Result, State, check_levels

from ..lib.common import discover_gui_single, source


def expiry_date(text):
    """
    Extract the support expiry date from a license description.

    Input:
        text: Text to parse.

    Output:
        Expiry as a date object, or None if no supported date can be parsed.

    """
    # Prefer a labelled expiry if the description also contains start/registration dates.
    match = re.search(r'(?:expir\w*|valid\s+until)\s*[:=]?\s*(?:on\s+)?(.+)', text, re.I)
    candidate = match.group(1) if match else text
    formats = ((r'\b\d{4}-\d{2}-\d{2}\b', '%Y-%m-%d'),
               (r'\b\d{4}/\d{2}/\d{2}\b', '%Y/%m/%d'),
               (r'\b\d{1,2}-[A-Za-z]{3}-\d{4}\b', '%d-%b-%Y'),
               (r'\b[A-Za-z]{3}\s+\d{1,2},?\s+\d{4}\b', '%b %d %Y'))
    for pattern, fmt in formats:
        for raw in re.findall(pattern, candidate):
            try:
                return datetime.strptime(raw.replace(',', ''), fmt).date()
            except ValueError:
                continue
    return None


def check_support(params, section):
    """
    Evaluate support and report monitoring results.

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
    licenses = data.get('licenses')
    license_key = 'FMWR'
    if isinstance(licenses, dict) and 'FMWR' not in licenses and 'FCEM' in licenses:
        license_key = 'FCEM'
    raw = licenses.get(license_key) if isinstance(licenses, dict) else None
    if not isinstance(raw, dict):
        yield Result(state=State.UNKNOWN, summary='Missing support license (FMWR / FCEM)')
        return
    status = raw.get('status')
    text = str(raw.get('txt') or '')
    token = str(status).strip().casefold() if status is not None else ''
    valid = {str(v).strip().casefold() for v in params['valid_statuses']}
    if token in ('expired', 'invalid', 'unlicensed', 'disabled'):
        state = State.CRIT
    elif token and token in valid:
        state = State.OK
    else:
        state = State.UNKNOWN
    yield Result(state=state, summary=f'Support status ({license_key}): {status if status is not None else "missing"}', details=text)
    expires = expiry_date(text)
    if expires is None:
        yield Result(state=State.UNKNOWN, summary=f'No supported expiry date in licenses.{license_key}.txt')
        return
    days = (expires - datetime.now(timezone.utc).date()).days
    yield Result(state=State.OK, summary='Expiry: ' + expires.isoformat())
    yield from check_levels(days, levels_lower=params['expiry'], metric_name='faz_support_days',
                            label='Remaining days', render_func=lambda value: f'{value:.0f} days')
    if days < 0:
        yield Result(state=State.CRIT, summary='Support has expired')


check_plugin_fortianalyzer_support = CheckPlugin(
    name='fortianalyzer_support', sections=['fortianalyzer'], service_name='FortiAnalyzer Support',
    discovery_function=discover_gui_single, check_function=check_support,
    check_ruleset_name='fortianalyzer_support', check_default_parameters={
        'expiry': ('fixed', (30, 14)), 'valid_statuses': ['valid', 'active', 'licensed', 'ok']})
