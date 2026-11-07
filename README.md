# API-based Checkmk Plugin for FortiAnalyzer

[<img src="docs/assets/octicons/download-16.svg" width="16" height="16" alt=""> Download MKP](https://github.com/networkautomation-ch/checkmk_fortianalyzer/releases/latest) · [<img src="docs/assets/octicons/book-16.svg" width="16" height="16" alt=""> Installation](#installation)

[<img src="docs/assets/octicons/bug-16.svg" width="16" height="16" alt=""> Report a Bug](https://github.com/networkautomation-ch/checkmk_fortianalyzer/issues/new?title=Bug%3A%20) · [<img src="docs/assets/octicons/light-bulb-16.svg" width="16" height="16" alt=""> Request a Feature](https://github.com/networkautomation-ch/checkmk_fortianalyzer/issues/new?title=Feature%3A%20) · [<img src="docs/assets/octicons/git-pull-request-16.svg" width="16" height="16" alt=""> Contribute](CONTRIBUTING.md)

---

Author: **Mayuran Asairatnam** · Package: **check_fortianalyzer**

Monitor FortiAnalyzer through a native special agent without an appliance agent.
Choose **Admin user** for full scope plus optional SSH volume, or **API user** for system information and ADOM log rates using a token.

## Admin user vs API user

| Service / function | Admin user (default) | API user |
| --- | --- | --- |
| Credentials | API user name and password | API token only |
| FortiAnalyzer System Hostname | Yes | Yes |
| FortiAnalyzer System Version | Yes | Yes |
| FortiAnalyzer System Serial Number | Yes | Yes |
| FortiAnalyzer System Platform Type | Yes | Yes |
| FortiAnalyzer System Max Number of Admin Domains | Yes | Yes |
| FortiAnalyzer ADOM &lt;Name&gt; Log Metrics — rate, devices, VDOMs | Yes | Yes |
| FortiAnalyzer Total Log Metrics — aggregate rate | Yes | Yes |
| FortiAnalyzer API — query status | Yes | Yes |
| FortiAnalyzer Device License | Yes | Not collected |
| FortiAnalyzer Managed Devices — FortiGates / Logging Devices | Yes | Not collected |
| FortiAnalyzer Resources — CPU, memory and disk | Yes | Not collected |
| FortiAnalyzer Support — status and expiry | Yes | Not collected |
| SSH daily volume / CLI average in ADOM and Total Log Metrics | Optional | Silently skipped |
| ADOM exclusions | Yes | Yes |
| Graphs for collected metrics | Yes | Yes; system capacity, rates and ADOM counts |
| Session login / logout | Yes | No; Bearer token |
| GUI proxy queries for license and resources | Yes | No |

After switching to **API user**, activate changes, run **Rescan → Remove vanished
services** to remove the four GUI-dependent services. Existing services can stay
UNKNOWN until removed. Log Metrics services remain without SSH volume metrics.
See [authentication](docs/authentication.md) for permissions and limitations.

## Installation

1. Download and enable the MKP under **Setup → Maintenance → Extension packages**.
2. Create the monitoring host with **Configured API integrations, no Checkmk agent**.
3. In **Setup**, search for **FortiAnalyzer**, create an integration rule and restrict it to the host.
4. Enter the required credentials and review the monitoring scope and connection settings.
5. Save the rule, activate changes, run service discovery and accept the services.

See [installation](docs/installation.md) for the exact fields and defaults,
[authentication](docs/authentication.md) for account permissions, and
[monitoring](docs/monitoring.md) for services and thresholds.

## Tested environments

| Component | Tested versions |
| --- | --- |
| FortiAnalyzer | 7.6.7, 7.6.8 |
| Checkmk | 2.4, 2.5 |

## Documentation

| Guide | Contents |
| --- | --- |
| [Installation](docs/installation.md) | Host setup, settings, CLI, discovery, ADOM exclusions and SSH |
| [Authentication and API access](docs/authentication.md) | Methods, secrets, permissions, endpoints, sessions and errors |
| [Monitoring reference](docs/monitoring.md) | All services, metrics, thresholds, calculations, units and graphs |
| [Development](docs/development.md) | Source layout, data flow, tests, MKP builds, CI/releases and references |

## Contributing and license

Independent community plugin. Not affiliated with or endorsed by Fortinet.

See the [Contributing Guidelines](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md).
Licensed under [GPL-2.0-or-later](LICENSE). Copyright (C) 2026 Mayuran Asairatnam.
Provided without warranty; appliance licenses/support are separate from this software license.

Icons: [GitHub Octicons](https://github.com/primer/octicons), licensed under [MIT](docs/assets/octicons/LICENSE).
