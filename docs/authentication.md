# Authentication and API access

[← README](../README.md) · [Installation](installation.md) · [Authentication](authentication.md) · [Monitoring](monitoring.md) · [Development](development.md)

## Required account and permissions

Use a dedicated account with JSON-RPC read access, access to the Logview
endpoints and access to every monitored ADOM. The required admin profile depends
on the FortiAnalyzer version and GUI endpoints. Restricted profiles may deny
GUI proxy access in Admin user mode, which is reported as an error.

### Authentication methods

The required **Authentication method** selection displays the matching credentials:

| Method | Credentials shown below the selection | Collection scope |
| --- | --- | --- |
| **Admin user** (default) | Required **API user name** and **API password** | JSON-RPC, GUI proxy and optional SSH |
| **API user** | Only **API token** | JSON-RPC system information and ADOM log statistics |

Use an API account/token supported by your FortiAnalyzer firmware and permit
requests from the Checkmk server's source address. Both methods need read access
to every monitored ADOM and the Logview endpoints. Admin user additionally needs
access to the GUI endpoints; optional SSH needs CLI permission. Do not assume
that an API user can access the GUI proxy just because JSON-RPC requests succeed.
See the [service comparison](../README.md#admin-user-vs-api-user).

### Admin user login and session lifecycle

Configure the dedicated account's username and password in the **FortiAnalyzer**
rule under **Authentication method → Admin user** (the default).
`Client.login()` sends an HTTPS POST to `/jsonrpc` with this body
(placeholder credentials):

```json
{
  "id": 1,
  "jsonrpc": "2.0",
  "method": "exec",
  "params": [{
    "url": "/sys/login/user",
    "data": {"user": "svc.monitoring", "passwd": "<password>"}
  }]
}
```

The response must contain a successful `result.status.code` (`0`, also accepted
as the string `"0"`) and a non-empty top-level `session` string. For example:

```json
{"result": [{"status": {"code": 0}}], "session": "<session-id>"}
```

`Client.call()` includes that session in subsequent JSON-RPC request bodies.
GUI proxy requests use the `CURRENT_SESSION` cookie instead. `collect()`
requests logout in its `finally` block, and `Client.logout()` clears the local
session even if the logout request fails. A failed login stops data collection
and appears in the API service and affected monitoring services.

### API user token behavior and migration

With **API user**, the collector sends `Authorization: Bearer <token>` on
JSON-RPC requests. It makes no login, logout, GUI proxy or SSH requests.
Device License, Managed Devices, Resources and Support services are not
discovered in this mode. System information and ADOM log rates remain monitored.
After switching an existing host to API user, activate changes and run
**Rescan → Remove vanished services** to remove the four GUI-dependent services.
Until removed, existing services can report UNKNOWN for missing API sections.
Switching back to Admin user enables their discovery again. SSH settings can
remain saved in token rules but are silently ignored.

Existing flat rules are automatically migrated to the nested `authentication`
structure, retaining credentials, the selected method (defaulting to password
for older rules), and other settings. Select **API user** and set **API token**
explicitly when changing a former password rule; migration does not convert an
admin password into a token. The saved shapes are shown below (`<Checkmk-Secret>`
is a placeholder, not literal Python):

```python
# Admin user
"authentication": ("password", {"user": "monitoring", "password": <Checkmk-Secret>})
# API user
"authentication": ("token", <Checkmk-Secret>)
```

If optional SSH collection is enabled, the same Admin user account and password are used
for SSH. The account also needs SSH access and permission to run the diagnostic
command described under [Optional SSH log volume](installation.md#optional-ssh-log-volume).

### API endpoints

All API calls are HTTPS POST requests. The selected method determines which
endpoints are queried:

| HTTPS path | Method | API URL | Authentication |
| --- | --- | --- | --- |
| `/jsonrpc` | `exec` | `/sys/login/user` | Admin user only |
| `/jsonrpc` | `get` | `/sys/status` | Both methods |
| `/cgi-bin/module/flatui_proxy` | `get` | `/gui/sys/license` | Admin user only |
| `/cgi-bin/module/flatui_proxy` | `get` | `/gui/sys/resource/realtime` | Admin user only |
| `/jsonrpc` | `get` | `/dvmdb/adom` | Both methods |
| `/jsonrpc` | `get` | `/logview/adom/<URL-encoded ADOM>/logstats`, `apiver=3` | Both methods |
| `/jsonrpc` | `exec` | `/sys/logout` | Admin user only |

JSON-RPC uses `params`, `id` and `jsonrpc`. Admin user adds the login session;
API user adds the Bearer header and no session. Logstats requests include `apiver: 3` inside the relevant
`params` object. GUI proxy calls use a flat body such as
`{"method":"get","url":"/gui/sys/license"}` and the `CURRENT_SESSION` cookie.

Standard responses must contain `status.code = 0`. The documented Logview v3
response may contain a single `result` object with `data` and no `status`.
This exception applies only to logstats; explicit API errors are still rejected.
Result lists are supported as well.

GUI proxy endpoints depend on firmware. The tested firmware versions are listed
under [Tested environments](../README.md#tested-environments). For UNKNOWN states, check the
API service, account permissions and response fields first. Invalid values are
not replaced with fabricated zeros.

## Error handling and password protection

- Configure Admin user credentials or an API token in the FortiAnalyzer rule.
  Checkmk supplies passwords and tokens through secret references; credentials
  do not need to be added to plugin files.
- Plaintext passwords and tokens are not passed in process arguments, and API responses
  are not dumped into service output.
- HTTP, TLS, timeout, JSON-RPC and missing-field errors produce error states.
  Failed queries do not produce fabricated measurements.
- Partial API failures preserve successfully collected sections.
- TLS certificates use Python's trust store by default; verification can be
  explicitly disabled.
- Redirects are not followed. Environment proxies are ignored.

Secrets remain Checkmk `Secret` objects in the server-side command builder.
The collector receives `--password-id ID:FILE` or `--api-token-id ID:FILE` and
resolves the reference inside its own process through Checkmk's password store.
No plaintext credential is supplied as a process argument. Token mode supplies
no username. Invalid or empty secrets and invalid token header characters are
rejected without echoing the secret. Lookup failures use sanitized diagnostics.

The API service reports collection errors as CRIT. Dependent checks report
UNKNOWN when their data is missing or invalid. Skipped GUI/SSH collection in API
user mode produces no error. Existing GUI services must be removed through
[service discovery](installation.md#switching-authentication-methods).

In Admin user mode, logout runs in `finally`; a failed logout is reported by the
API service, and server-side closure cannot be guaranteed without a response.
The timeout applies per request. A successful run makes
`6 + number of monitored ADOMs` requests with Admin user, including login and
logout, or `2 + number of monitored ADOMs` with API user. Allow for this in the
Checkmk data source time limit. ADOM requests run sequentially.

For rate coverage, empty results and partial ADOM failures, see
[Log rates and partial results](monitoring.md#log-rates-and-partial-results).
