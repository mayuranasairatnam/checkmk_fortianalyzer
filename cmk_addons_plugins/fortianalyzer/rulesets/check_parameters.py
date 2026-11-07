"""
Threshold rules for FortiAnalyzer checks.
"""
from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    DefaultValue, DictElement, Dictionary, Float, Integer, LevelDirection, LevelsType, List, Percentage,
    SimpleLevels, SingleChoice, SingleChoiceElement, String,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, HostAndItemCondition, HostCondition, Topic


def utilization(title):
    """
    Build the Checkmk configuration form for utilization.

    Input:
        title: Title displayed in the configuration form.

    Output:
        Required DictElement containing percentage warning and critical levels.

    """
    return DictElement(required=True, parameter_form=SimpleLevels[float](
        title=Title(title), form_spec_template=Percentage(), level_direction=LevelDirection.UPPER,
        prefill_fixed_levels=DefaultValue((80.0, 90.0))))


def license_form():
    """
    Build the Checkmk configuration form for license.

    Input:
        None.

    Output:
        Dictionary form specification with defaults and validation rules.

    """
    return Dictionary(elements={'levels': utilization('Device license utilization')})


def resource_form():
    """
    Build the Checkmk configuration form for resource.

    Input:
        None.

    Output:
        Dictionary form specification with defaults and validation rules.

    """
    return Dictionary(elements={
        'cpu': utilization('CPU average'), 'memory': utilization('Memory utilization'),
        'disk': utilization('Disk utilization'),
        'memory_unit': DictElement(required=True, parameter_form=SingleChoice(
            title=Title('Unit of memory_used and memory_total in API response'),
            help_text=Help('Verify this unit against your FortiAnalyzer firmware. Percentages are not converted.'),
            elements=[SingleChoiceElement(name='bytes', title=Title('Bytes')),
                      SingleChoiceElement(name='kib', title=Title('KiB')),
                      SingleChoiceElement(name='mib', title=Title('MiB')),
                      SingleChoiceElement(name='gb', title=Title('GB (decimal)')),
                      SingleChoiceElement(name='gib', title=Title('GiB (binary)'))], prefill=DefaultValue('kib'))),
    })


def support_form():
    """
    Build the Checkmk configuration form for support.

    Input:
        None.

    Output:
        Dictionary form specification with defaults and validation rules.

    """
    return Dictionary(elements={
        'expiry': DictElement(required=True, parameter_form=SimpleLevels[int](
            title=Title('Remaining support lifetime'), form_spec_template=Integer(unit_symbol='days'),
            level_direction=LevelDirection.LOWER, prefill_fixed_levels=DefaultValue((30, 14)))),
        'valid_statuses': DictElement(parameter_form=List(
            title=Title('API status values indicating valid support'), element_template=String(),
            help_text=Help('Default valid values: valid, active, licensed, ok. Configuring this list replaces these defaults. Unknown and undocumented numeric statuses remain UNKNOWN. Add the numeric value as a string only after verifying its meaning for your firmware.'))),
    })


rule_spec_fortianalyzer_license = CheckParameters(
    name='fortianalyzer_license', title=Title('FortiAnalyzer device license utilization'),
    topic=Topic.APPLICATIONS, parameter_form=license_form, condition=HostCondition())
rule_spec_fortianalyzer_resources = CheckParameters(
    name='fortianalyzer_resources', title=Title('FortiAnalyzer resources'),
    topic=Topic.APPLICATIONS, parameter_form=resource_form, condition=HostCondition())
rule_spec_fortianalyzer_support = CheckParameters(
    name='fortianalyzer_support', title=Title('FortiAnalyzer support expiration'),
    topic=Topic.APPLICATIONS, parameter_form=support_form, condition=HostCondition())


def lograte_form():
    """
    Build the Checkmk configuration form for log rate.

    Input:
        None.

    Output:
        Dictionary form specification with defaults and validation rules.

    """
    return Dictionary(elements={
        'volume_levels': DictElement(parameter_form=SimpleLevels[float](
            title=Title('Upper levels on daily log volume (SSH)'), form_spec_template=Float(unit_symbol='GB/day'),
            level_direction=LevelDirection.UPPER, prefill_levels_type=DefaultValue(LevelsType.NONE),
            prefill_fixed_levels=DefaultValue((20.0, 25.0)))),
        'upper': DictElement(required=True, parameter_form=SimpleLevels[float](
            title=Title('Upper levels on log rate'), form_spec_template=Float(unit_symbol='logs/s'),
            level_direction=LevelDirection.UPPER, prefill_levels_type=DefaultValue(LevelsType.NONE),
            prefill_fixed_levels=DefaultValue((10000.0, 20000.0)))),
        'lower': DictElement(required=True, parameter_form=SimpleLevels[float](
            title=Title('Lower levels on log rate'), form_spec_template=Float(unit_symbol='logs/s'),
            level_direction=LevelDirection.LOWER, prefill_levels_type=DefaultValue(LevelsType.NONE),
            prefill_fixed_levels=DefaultValue((10.0, 1.0)))),
    })


rule_spec_fortianalyzer_adom_lograte = CheckParameters(
    name='fortianalyzer_adom_lograte', title=Title('FortiAnalyzer ADOM log metrics'),
    topic=Topic.APPLICATIONS, parameter_form=lograte_form,
    condition=HostAndItemCondition(item_title=Title('ADOM')))
rule_spec_fortianalyzer_total_lograte = CheckParameters(
    name='fortianalyzer_total_lograte', title=Title('FortiAnalyzer total log metrics'),
    topic=Topic.APPLICATIONS, parameter_form=lograte_form, condition=HostCondition())


def logvolume_form():
    """
    Build the Checkmk configuration form for log volume.

    Input:
        None.

    Output:
        Dictionary form specification with defaults and validation rules.

    """
    return Dictionary(elements={
        'levels': DictElement(required=True, parameter_form=SimpleLevels[float](
            title=Title('Daily log volume'), form_spec_template=Float(unit_symbol='GB/day'),
            level_direction=LevelDirection.UPPER, prefill_levels_type=DefaultValue(LevelsType.NONE),
            prefill_fixed_levels=DefaultValue((20.0, 25.0)))),
    })


rule_spec_fortianalyzer_adom_logvolume = CheckParameters(
    name='fortianalyzer_adom_logvolume', title=Title('FortiAnalyzer ADOM daily log volume'),
    topic=Topic.APPLICATIONS, parameter_form=logvolume_form,
    condition=HostAndItemCondition(item_title=Title('ADOM')))
rule_spec_fortianalyzer_total_logvolume = CheckParameters(
    name='fortianalyzer_total_logvolume', title=Title('FortiAnalyzer total daily log volume'),
    topic=Topic.APPLICATIONS, parameter_form=logvolume_form, condition=HostCondition())
