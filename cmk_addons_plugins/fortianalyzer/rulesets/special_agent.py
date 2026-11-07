"""
FortiAnalyzer datasource configuration.
"""
from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    CascadingSingleChoice, CascadingSingleChoiceElement,
    DefaultValue, DictElement, Dictionary, Integer, Password, SingleChoice,
    SingleChoiceElement, String, migrate_to_password, validators,
)
from cmk.rulesets.v1.rule_specs import SpecialAgent, Topic

# These extended forms support list defaults without changing saved rule values.
try:
    from cmk.rulesets.internal.form_specs import ListExtended
except ImportError:  # Checkmk 2.4
    from cmk.gui.form_specs.private.list_extended import ListExtended

try:
    from cmk.gui.form_specs.unstable.dictionary_extended import DictionaryExtended
except ImportError:  # Checkmk 2.4
    from cmk.gui.form_specs.private.dictionary_extended import DictionaryExtended


DEFAULT_EXCLUDED_ADOMS = (
    'FortiAnalyzer',
    'FortiAuthenticator',
    'FortiCache',
    'FortiCarrier',
    'FortiClient',
    'FortiDDoS',
    'FortiDeceptor',
    'FortiFirewall',
    'FortiFirewallCarrier',
    'FortiMail',
    'FortiManager',
    'FortiProxy',
    'FortiSandbox',
    'FortiWeb',
    'Syslog',
    'Unmanaged_Devices',
    'others',
    'rootp',
)


def _new_rule_defaults():
    """
    Activate new-rule exclusions when the installed form supports it.

    Input:
        DictionaryExtended implementation provided by the installed Checkmk version.

    Output:
        Constructor options enabling exclusions on newer forms, or no options
        for Checkmk 2.4. Saved exclusions and explicitly empty lists are retained.

    """
    if 'default_checked' in DictionaryExtended.__dataclass_fields__:
        return {'default_checked': ['exclude_adoms']}
    return {}


def migrate_ssh_settings(value):
    """
    Normalize legacy SSH options to the current configuration format.

    Input:
        value: Raw value to validate or convert.

    Output:
        Migrated rule value; values outside the handled legacy format pass through.

    """
    if isinstance(value, dict):
        return {key: item for key, item in value.items() if key == 'port'}
    return value


def migrate_password_fields(value):
    """
    Nest saved credentials and remove obsolete address, CA bundle and SSH overrides.

    Input:
        value: Raw value to validate or convert.

    Output:
        Migrated rule value; values outside the handled legacy format pass through.

    """
    if not isinstance(value, dict):
        return value
    value = dict(value)
    value.pop('address', None)
    value.pop('ca_file', None)
    value.pop('ssh_password', None)
    if 'authentication' not in value and 'password' in value:
        method = value.pop('auth_method', 'password')
        secret = value.pop('password')
        user = value.pop('user', '')
        value['authentication'] = (
            method, secret if method == 'token' else {'user': user, 'password': secret})
    if 'ssh_logvolume' in value:
        value['ssh_logvolume'] = migrate_ssh_settings(value['ssh_logvolume'])
    return value


def parameter_form():
    """
    Build the Checkmk configuration form for special agent settings.

    Input:
        None.

    Output:
        Dictionary form specification with defaults and validation rules.

    """
    return DictionaryExtended(**_new_rule_defaults(), migrate=migrate_password_fields, elements={
        'authentication': DictElement(required=True, parameter_form=CascadingSingleChoice(
            title=Title('Authentication method'),
            prefill=DefaultValue('password'),
            elements=[
                CascadingSingleChoiceElement(
                    name='password', title=Title('Admin user'),
                    parameter_form=Dictionary(elements={
                        'user': DictElement(required=True, parameter_form=String(
                            title=Title('API user name'),
                            custom_validate=(validators.LengthInRange(min_value=1),))),
                        'password': DictElement(required=True, parameter_form=Password(
                            title=Title('API password'), migrate=migrate_to_password)),
                    })),
                CascadingSingleChoiceElement(
                    name='token', title=Title('API user'),
                    parameter_form=Password(title=Title('API token'), migrate=migrate_to_password)),
            ],
            help_text=Help('Admin user uses a username and password. API user uses the generated token of a REST API Admin.'))),
        'port': DictElement(parameter_form=Integer(title=Title('HTTPS port'), prefill=DefaultValue(443),
            custom_validate=(validators.NetworkPort(),))),
        'timeout': DictElement(parameter_form=Integer(title=Title('Timeout per API request'),
            unit_symbol='seconds', prefill=DefaultValue(30),
            custom_validate=(validators.NumberInRange(min_value=1, max_value=300),))),
        'tls': DictElement(parameter_form=SingleChoice(title=Title('TLS certificate verification'),
            elements=[SingleChoiceElement(name='verify', title=Title('Verify certificate')),
                      SingleChoiceElement(name='skip', title=Title('Skip certificate verification'))],
            prefill=DefaultValue('verify'))),
        'ssh_logvolume': DictElement(parameter_form=Dictionary(
            migrate=migrate_ssh_settings,
            title=Title('ADOM log volume via SSH (optional)'),
            help_text=Help('Runs diagnose fortilogd logvol-adom all using the API address and Admin user credentials. Only used with Admin user authentication; ignored for API user. SSH host keys are accepted automatically. Requires Paramiko in the Checkmk Python environment.'),
            elements={
                'port': DictElement(parameter_form=Integer(title=Title('SSH port'), prefill=DefaultValue(22), custom_validate=(validators.NetworkPort(),))),
            })),
        'exclude_adoms': DictElement(parameter_form=ListExtended(
            title=Title('ADOMs excluded from log monitoring'),
            prefill=DefaultValue(list(DEFAULT_EXCLUDED_ADOMS)),
            element_template=String(custom_validate=(validators.LengthInRange(min_value=1),)),
            help_text=Help('Exact ADOM names. The list is prefilled with suggested ADOMs; on Checkmk 2.4, enable this option to apply them. Edit or clear the list to change the monitoring scope. Only exclude ADOMs you deliberately do not monitor; API errors are not automatically ignored. The total then covers the remaining visible ADOMs.'))),
    })


rule_spec_fortianalyzer = SpecialAgent(
    name='fortianalyzer', title=Title('FortiAnalyzer'),
    topic=Topic.NETWORKING, parameter_form=parameter_form)
