"""
Compatibility imports for precompiled FortiAnalyzer checks created before the module split.

Implementations and plugin registrations live in the feature modules. Historical
attributes are resolved on demand so existing compiled imports keep working,
without exposing duplicate registrations during plugin discovery.
"""

from . import fortianalyzer_adoms as _adoms
from . import fortianalyzer_api as _api
from . import fortianalyzer_license as _license
from . import fortianalyzer_logvolume as _logvolume
from . import fortianalyzer_managed as _managed
from . import fortianalyzer_resources as _resources
from . import fortianalyzer_support as _support
from . import fortianalyzer_system as _system
from ..lib import common as _common


_EXPORTS = {
    'RESOURCE_MEMORY': _resources.RESOURCE_MEMORY,
    'RESOURCE_PERCENTAGES': _resources.RESOURCE_PERCENTAGES,
    'SYSTEM_FIELDS': _system.SYSTEM_FIELDS,
    'agent_section_fortianalyzer': _api.agent_section_fortianalyzer,
    'check_adom_logvolume': _logvolume.check_adom_logvolume,
    'check_adom_rates': _adoms.check_adom_rates,
    'check_adoms': _adoms.check_adoms,
    'check_api': _api.check_api,
    'check_combined_resources': _resources.check_combined_resources,
    'check_license': _license.check_license,
    'check_lograte': _adoms.check_lograte,
    'check_logvolume': _logvolume.check_logvolume,
    'check_managed': _managed.check_managed,
    'check_plugin_fortianalyzer_adom_logvolume': _logvolume.check_plugin_fortianalyzer_adom_logvolume,
    'check_plugin_fortianalyzer_adoms': _adoms.check_plugin_fortianalyzer_adoms,
    'check_plugin_fortianalyzer_api': _api.check_plugin_fortianalyzer_api,
    'check_plugin_fortianalyzer_license': _license.check_plugin_fortianalyzer_license,
    'check_plugin_fortianalyzer_managed': _managed.check_plugin_fortianalyzer_managed,
    'check_plugin_fortianalyzer_resources': _resources.check_plugin_fortianalyzer_resources,
    'check_plugin_fortianalyzer_resources_combined': _resources.check_plugin_fortianalyzer_resources_combined,
    'check_plugin_fortianalyzer_support': _support.check_plugin_fortianalyzer_support,
    'check_plugin_fortianalyzer_system': _system.check_plugin_fortianalyzer_system,
    'check_plugin_fortianalyzer_total': _adoms.check_plugin_fortianalyzer_total,
    'check_plugin_fortianalyzer_total_logvolume': _logvolume.check_plugin_fortianalyzer_total_logvolume,
    'check_resources': _resources.check_resources,
    'check_support': _support.check_support,
    'check_system': _system.check_system,
    'check_total': _adoms.check_total,
    'check_total_logvolume': _logvolume.check_total_logvolume,
    'check_total_rates': _adoms.check_total_rates,
    'count': _common.count,
    'discover_adoms': _adoms.discover_adoms,
    'discover_logvolume': _logvolume.discover_logvolume,
    'discover_resources': _resources.discover_resources,
    'discover_retired_resources': _resources.discover_retired_resources,
    'discover_single': _common.discover_single,
    'discover_gui_single': _common.discover_gui_single,
    'discover_system': _system.discover_system,
    'discover_total_logvolume': _logvolume.discover_total_logvolume,
    'expiry_date': _support.expiry_date,
    'log_values': _adoms.log_values,
    'number': _common.number,
    'parse_fortianalyzer': _api.parse_fortianalyzer,
    'source': _common.source,
    'volume_rows': _logvolume.volume_rows,
}


def __getattr__(name):
    """
    Resolve a historical function, constant or plugin registration by name.

    Input:
        name: Attribute imported by a previously compiled Checkmk check.

    Output:
        The original object from its feature module; raises AttributeError for
        names outside the compatibility exports.

    """
    try:
        return _EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
