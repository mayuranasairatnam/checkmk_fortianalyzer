"""
Checkmk safely supplies the password store reference, never the password argv.
"""
from cmk.server_side_calls.v1 import Secret, SpecialAgentCommand, SpecialAgentConfig, noop_parser


def commands(params, host_config):
    """
    Build the special agent invocation from validated host settings.

    Input:
        params: Validated special agent settings from the Checkmk rule.
        host_config: Checkmk host configuration used to resolve the target address.

    Output:
        Yields SpecialAgentCommand objects containing the agent arguments.

    """
    address = host_config.primary_ip_config.address
    if not address:
        address = host_config.name
    args = ['--address', address,
            '--port', str(params.get('port', 443)), '--timeout', str(params.get('timeout', 30))]
    if 'authentication' in params:
        method, credentials = params['authentication']
    else:
        # Rules saved before credentials were grouped under authentication.
        method = params.get('auth_method', 'password')
        credentials = params['password'] if method == 'token' else params
    if method not in ('password', 'token'):
        raise ValueError('Unsupported authentication method')
    secret = credentials if method == 'token' else credentials['password']
    if method == 'token':
        args.extend(['--api-token-id', secret])
    elif method == 'password':
        if not credentials.get('user'):
            raise ValueError('API user name is required for password authentication')
        args.extend(['--user', credentials['user'], '--password-id', secret])
    if not isinstance(secret, Secret):
        raise TypeError('Expected a Checkmk Secret')
    if params.get('tls', 'verify') == 'skip':
        args.append('--no-cert-check')
    for adom in params.get('exclude_adoms', []):
        args.extend(['--exclude-adom', adom])
    if method == 'password' and 'ssh_logvolume' in params:
        args.extend(['--ssh-logvolume', '--ssh-port', str(params['ssh_logvolume'].get('port', 22))])
    yield SpecialAgentCommand(command_arguments=args)


special_agent_fortianalyzer = SpecialAgentConfig(
    name='fortianalyzer', parameter_parser=noop_parser, commands_function=commands)
