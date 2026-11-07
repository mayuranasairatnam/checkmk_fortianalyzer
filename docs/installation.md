# Installation and configuration

[← README](../README.md) · [Installation](installation.md) · [Authentication](authentication.md) · [Monitoring](monitoring.md) · [Development](development.md)

## Requirements

- Checkmk **2.4 or 2.5**, with Python **3.11+** and `requests` in the site environment.
- HTTPS access from the Checkmk site to the FortiAnalyzer appliance.
- A dedicated account or API token with the [required permissions](authentication.md).

## Install the package

Download the MKP using **Download MKP** in the [README](../README.md), then upload
and enable it under **Setup → Maintenance → Extension packages**. The package ID
is `check_fortianalyzer`. No Checkmk agent is required on the monitored system.

Alternatively, as the Checkmk site user, replace `VERSION` with the downloaded
package version:

```sh
mkp add /path/to/check_fortianalyzer-VERSION.mkp
mkp enable check_fortianalyzer VERSION
```

To build locally, run `python3 -B build_mkp.py` from the repository directory.
See [development](development.md) for local setup and checks.

## Configure the host and rule

1. Create a FortiAnalyzer host with the appliance's DNS name or IP address.
   Select **Configured API integrations, no Checkmk agent** as the data source.
2. In **Setup**, search for **FortiAnalyzer** and open the integration ruleset.
   Create a new rule and restrict its **Conditions → Explicit hosts** to the
   host created above.
3. Select **Authentication method** and enter the matching credentials:

   | Authentication method | Required fields |
   | --- | --- |
   | **Admin user** (default) | **API user name** and **API password** |
   | **API user** | **API token** |

   Use the Checkmk Password Store for passwords and tokens.
4. Review **ADOMs excluded from monitoring**. Checkmk 2.5 enables the
   prefilled list for new rules; in Checkmk 2.4, enable it manually if needed.
   See [Default ADOM exclusions](#default-adom-exclusions).
5. Review the [connection settings](#connection-settings), then save the rule.
6. Activate changes and continue with [service discovery](#discover-and-check-services).

## Connection settings

| Setting | Default / behavior |
| --- | --- |
| Target address | Checkmk host primary address; falls back to the host name |
| HTTPS port | 443; configurable from 1 to 65535 |
| Timeout per API request | 30 seconds; rule accepts 1 to 300 seconds |
| TLS certificate verification | Enabled; uses the Python environment's default trust store |
| SSH log volume | Disabled; Admin user only |
| SSH port | 22; configurable from 1 to 65535 |

The certificate must match the target address. Disable verification only through
the explicit TLS option when required. Current rules have no separate API address,
CA bundle, SSH account or SSH target override. Authentication and permission
requirements are described in [Authentication and API access](authentication.md).

## Discover and check services

Run service discovery on the host, accept the discovered services and activate
changes. Inspect **FortiAnalyzer API** for collection errors. After changing the
monitoring scope, rescan the host and use **Remove vanished services** for items
that are no longer monitored.

New ADOMs appear during normal service discovery. Configure periodic service
discovery if new services should be accepted automatically. Removed ADOMs can
remain UNKNOWN until their vanished services are removed. A failed ADOM list
query does not remove stored services.

As the Checkmk site user, run discovery and check the result:

```sh
cmk -vI YOUR_HOST
cmk -nv YOUR_HOST
```

## Default ADOM exclusions

In Checkmk 2.5, new rules enable the optional exclusion list automatically.
In Checkmk 2.4, enable the option manually to apply the exclusions.
In both versions, the list is prefilled with these exact names:

```text
FortiAnalyzer
FortiAuthenticator
FortiCache
FortiCarrier
FortiClient
FortiDDoS
FortiDeceptor
FortiFirewall
FortiFirewallCarrier
FortiMail
FortiManager
FortiProxy
FortiSandbox
FortiWeb
Syslog
Unmanaged_Devices
others
rootp
```

The list is editable: remove an entry to monitor that ADOM, add other names,
clear the list, or disable the option. Matching is exact and case-sensitive.
Names absent from the appliance have no effect. Other visible ADOMs, including
`root` and `test`, remain eligible for discovery.

Exclusions apply to ADOM-specific collection and discovery. The collector
records which configured names matched the returned ADOM list. Global system,
license, managed-device, support and resource measurements (when collected)
continue to describe the whole appliance; their values are not reduced by the exclusion list.

For excluded ADOMs, API log-rate queries are skipped and returned SSH volume
rows are filtered out. The SSH command still retrieves appliance-wide output.
The API log-rate total covers the remaining API results; the SSH volume total
covers the remaining CLI rows. If SSH is disabled, API checks continue without
daily-volume or CLI-average metrics. Disabled SSH alone causes no error state.

### Existing rules and services

Updating the package does not add or replace exclusions in existing rules.
Saved custom lists stay unchanged, and empty or disabled lists remain empty
or disabled. To use the default exclusions in an existing rule:

1. Open the rule and enable its ADOM exclusion option if necessary.
2. Enter the names listed above, keeping any additional exclusions you need.
3. Save the rule and activate changes.
4. Run **Rescan** on the affected host, then select **Remove vanished services**
   to remove ADOM services that are no longer monitored.

## Optional SSH log volume

Enable **ADOM log volume via SSH (optional)** in the FortiAnalyzer rule and
optionally set the SSH port, which defaults to 22. SSH uses the API address,
Admin user name and password. SSH requires **Admin user** authentication;
with **API user**, SSH collection is silently skipped even if enabled in the rule.
The account must have SSH access and permission to run:

```text
diagnose fortilogd logvol-adom all
```

The Checkmk Python environment must provide Paramiko. As the site user, check:

```sh
python3 -c 'import paramiko; print(paramiko.__version__)'
```

Paramiko is not bundled in the MKP. The agent reports when it is unavailable.
Current rules have no separate SSH credentials or known_hosts settings; old
overrides are removed during migration and ignored before the rule is saved.
SSH host keys are accepted without verification, matching the existing behavior.

For volume metrics, units, dates and error states, see
[Daily log volume](monitoring.md#daily-log-volume).

The agent first requests a pseudo-terminal for SSH exec. If the response has
no readable volume data, or exec is rejected, it opens an interactive CLI shell
on the same authenticated connection. It waits for prompts, sends the fixed
diagnostic command, acknowledges pagers with spaces and removes ANSI sequences.
It does not change console settings. Output size and runtime are bounded.

SSH errors distinguish authentication, host key, key file, permissions, DNS,
network and algorithm failures. Arbitrary remote error text is not copied into
service output. For OpenSSH diagnostics on older configurations, run the same
command as the Checkmk site user with `-v`; a root session has a different key
and known_hosts context.

## Switching authentication methods

After switching to **API user**, save the rule, activate changes, run **Rescan**
and select **Remove vanished services**. Device License, Managed Devices,
Resources and Support are no longer discovered. Until removed, existing checks
can report UNKNOWN because the license/resource sections are absent. SSH volume
is silently skipped; ADOM and Total Log Metrics services remain with API rates
and no volume metrics. Switching back to **Admin user** makes the GUI-dependent
services eligible for discovery again; enable SSH separately if needed.

Retired standalone Log Volume and individual Resources services are kept
loadable for existing installations but are no longer discovered. Remove these
vanished services after accepting the combined Log Metrics and Resources services.
