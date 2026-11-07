"""
FortiAnalyzer: JSON section parser and API collection status check.
"""

import json

from cmk.agent_based.v2 import AgentSection, CheckPlugin, Result, State

from ..lib.common import discover_single


def parse_fortianalyzer(string_table):
    """
    Parse the JSON agent payload for FortiAnalyzer.

    Input:
        string_table: Checkmk section rows containing the JSON agent payload.

    Output:
        Parsed section data, or an API error section when the JSON payload is invalid.

    """
    try:
        data = json.loads(''.join(row[0] for row in string_table if row))
        if isinstance(data, dict):
            return data
    except (ValueError, TypeError):
        pass
    return {'api': {'errors': ['Invalid FortiAnalyzer agent data']}}


agent_section_fortianalyzer = AgentSection(name='fortianalyzer', parse_function=parse_fortianalyzer)


def check_api(section):
    """
    Evaluate API and report monitoring results.

    Input:
        section: Parsed agent data for the registered section.

    Output:
        Yields Checkmk Result objects with monitoring states and diagnostic details.

    """
    api = section.get('api')
    if not isinstance(api, dict) or not isinstance(api.get('errors'), list):
        yield Result(state=State.UNKNOWN, summary='Missing API collection status')
    elif api['errors']:
        yield Result(state=State.CRIT, summary='; '.join(str(e) for e in api['errors']))
    else:
        summary = 'All API queries successful'
        if section.get('authentication') != 'token':
            summary += '; session closed'
        yield Result(state=State.OK, summary=summary)


check_plugin_fortianalyzer_api = CheckPlugin(
    name='fortianalyzer_api', sections=['fortianalyzer'], service_name='FortiAnalyzer API',
    discovery_function=discover_single, check_function=check_api)
