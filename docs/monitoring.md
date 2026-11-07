# Services, metrics and thresholds

[← README](../README.md) · [Installation](installation.md) · [Authentication](authentication.md) · [Monitoring](monitoring.md) · [Development](development.md)

The descriptions below cover the full **Admin user** scope. **API user**
collects system information, ADOM/total log metrics and API status, without SSH
volume. See the [service comparison](../README.md#admin-user-vs-api-user).

## Monitoring scope and services

The special agent reads system, license, support and resource data through
HTTPS JSON-RPC and the GUI proxy. For every monitored ADOM, it collects log
rates and device/VDOM counts, then calculates a total across the monitored
API results. Optional SSH collection adds daily log volume and the CLI average.

| Service | Data / performance metrics |
| --- | --- |
| FortiAnalyzer System &lt;Field&gt; | One service each for Hostname, Version, Serial Number, Platform Type and Max Number of Admin Domains; `faz_max_adoms` |
| FortiAnalyzer Device License | `used_devices`, `licensed_devices`, `free_devices`, `utilization_percent` |
| FortiAnalyzer Managed Devices | FortiGates / Logging Devices; `faz_logging_devices` |
| FortiAnalyzer Support | Status, expiry date, remaining days; `faz_support_days` |
| FortiAnalyzer Resources | CPU, disk and memory utilization, memory used/total/free; `faz_cpu_percent`, `faz_disk_percent`, `faz_memory_percent`, `faz_memory_used`, `faz_memory_total`, `faz_memory_free` |
| FortiAnalyzer ADOM &lt;Name&gt; Log Metrics | `logs_per_second` or `faz_reported_logs_per_second`, `devices`, `vdoms`; optional SSH volume metrics |
| FortiAnalyzer Total Log Metrics | Complete or reported log rate across the monitored ADOMs; optional SSH volume metrics |
| FortiAnalyzer API | Collection errors, including failed logout |

System information uses dedicated services whose OK summaries contain the
individual API value, such as `CH-FAZ-001` or `10000`. Resources are displayed
in one combined service. Separate hardware/software inventory is not included.

Log rates are summed across all devices and VDOMs within an ADOM. The API
already supplies logs per second, so the plugin does not calculate another
counter delta. Historical graphs use Checkmk's normal recording from the start
of monitoring. Existing FortiAnalyzer time series are not imported.

The total Log Metrics service exports a rate and optional volume metrics, but
no aggregate `devices` or `vdoms` metric. Per-ADOM counts come from the `devs`
and `vdoms` lists returned by Logview; the appliance-wide logging-device count
comes separately from `dev_num_count.fgt_cnt.val`.

The five System fields are Hostname, Version, Serial Number, Platform Type and
Max Number of Admin Domains. Missing or invalid fields produce UNKNOWN; ADOM
capacity must be a non-negative integer.

## Rules and defaults

| Rule | Default WARN / CRIT |
| --- | --- |
| FortiAnalyzer device license utilization | 80 / 90% |
| FortiAnalyzer resources: CPU | 80 / 90% |
| FortiAnalyzer resources: memory | 80 / 90% |
| FortiAnalyzer resources: disk | 80 / 90% |
| FortiAnalyzer support expiration | Below 30 / 14 days |
| FortiAnalyzer ADOM log rate | Upper and lower levels disabled; configurable per ADOM |
| FortiAnalyzer total log rate | Upper and lower levels disabled |
| Daily log volume via SSH | Upper levels disabled; configurable for ADOM and total services |

### Device license calculation

The collector reads `/gui/sys/license` through the GUI proxy. The
**FortiAnalyzer Device License** check maps its fields as follows:

| API field / calculation | Metric | Meaning |
| --- | --- | --- |
| `current_num_dev` | `used_devices` | Used device capacity |
| `max_num_dev` | `licensed_devices` | Licensed device capacity |
| `max_num_dev - current_num_dev` | `free_devices` | Remaining device capacity |
| `current_num_dev / max_num_dev * 100` | `utilization_percent` | Device license utilization |

For example, 8 used devices and a capacity of 10 produce 2 free devices and
80% utilization, reaching the default WARN threshold. Missing or invalid
capacity fields produce UNKNOWN. The check uses the appliance's capacity
fields directly; it does not calculate license usage by adding up ADOM device
counts or the logging-device count. Support status and expiry are
evaluated separately by **FortiAnalyzer Support**.

Exceeded license capacity and expired support always cause CRIT. Zero capacity
prevents percentage calculation: the result is CRIT with devices in use,
otherwise UNKNOWN. Negative free capacity during overuse is retained.

### Resources and memory units

The resource rule defines the unit of API fields `memory_used` and
`memory_total`: **KiB** by default, with bytes, MiB, GB and GiB as alternatives.
Verify the unit against the appliance firmware. Metrics are stored in bytes;
the combined resource summary uses KiB/MiB/GiB. Utilization percentages come
directly from `cpu_avg`, `disk` and `memory`.

### Support status and expiry

Support uses `licenses.FMWR`, falling back to `licenses.FCEM` if FMWR is absent.
Valid statuses are `valid`, `active`, `licensed` and `ok`, ignoring case.
`expired`, `invalid`, `unlicensed` and `disabled` cause CRIT. Other values are
UNKNOWN unless configured as valid after their meaning has been verified.

Expiry dates are extracted from `txt` in these formats: `YYYY-MM-DD`,
`YYYY/MM/DD`, `DD-Mon-YYYY` or `Mon DD, YYYY`. Unsupported dates produce UNKNOWN.
Remaining days use the Checkmk server's UTC calendar date.

Graphs cover license counts, log rates, ADOM device/VDOM counts, resources and
memory. Generic license metrics and `devices` are not globally redefined here,
avoiding duplicate definitions when FortiManager is installed. They use
Checkmk's automatic rendering or existing FortiManager metric definitions.

### Graphs and units

The package defines combined and individual graphs for license counts and
utilization, ADOM devices/VDOMs, CPU/disk/memory percentages and memory sizes.
It also defines maximum ADOM capacity, logging-device count and support-lifetime
graphs, plus a device-license utilization perfometer with a 0–100% range.
Complete and incomplete log rates have separate graphs. Daily and CLI-average
volume each have a graph when SSH metrics are present. API user retains graphs
for the metrics it collects; it supplies no GUI or volume samples. Old samples
are not erased when switching methods, and new graphs require collected metrics.

Counts use integers, utilization uses percent, rates use logs/s and remaining
support lifetime uses days. Memory graph values use bytes with IEC rendering;
volume uses decimal GB/day.

### Log rates and partial results

- `data.devs = []` is a valid measurement of 0 logs/s, 0 devices and 0 VDOMs.
- Every device must contain a `vdoms` list. Present `lograte` values must be
  finite and non-negative. Negative values, `null`, malformed values and
  invalid lists are errors; they are not converted to zero.
- If individual VDOMs omit `lograte`, the service sums the available rates.
  Missing coverage is shown in the details. Missing individual
  fields alone do not cause WARN when at least one valid rate is available.
  Configured thresholds still apply. Partial rates use
  `faz_reported_logs_per_second`, with a separate graph; `logs_per_second`
  is reserved for complete coverage. If all VDOM rates are missing, the
  service is UNKNOWN without a rate metric. Device and VDOM counts remain
  available.
- Successful ADOMs remain usable when another ADOM fails. The total rate is
  UNKNOWN and exports no rate metric while an ADOM result is unavailable.
- A successfully retrieved empty ADOM list produces a valid total rate of zero.
- If all ADOM queries succeed but some VDOM rates are missing, the total uses
  the reported partial-rate metric and includes coverage details. Missing
  individual fields alone do not cause WARN; thresholds still apply.
- Totals cover ADOMs visible to the API user, minus explicit exclusions. The
  user therefore needs access to every ADOM intended for monitoring.
- ADOM requests run sequentially. The total is a sum of the returned values,
  not an exactly synchronized snapshot.

## Daily log volume

Daily volume and the CLI average appear in the ADOM and total Log Metrics
services as `faz_log_gb_day` and `faz_log_average_gb_day`. CLI KB/MB/GB/TB units
are converted in steps of 1024 to bytes and then to decimal GB. For example,
`279.27 MB` becomes `0.293 GB/day`, and an average of `317.23 MB` becomes
`0.333 GB/day`.

The date in the first CLI column remains visible. The daily value is the
running counter for that calendar date, not a 24-hour extrapolation. Older
values appear in service details but are not backfilled into Checkmk RRDs.
Dates more than two days old or more than one day in the future produce WARN
without a new volume measurement. ADOM exclusions also apply to volume data.

SSH failures cause UNKNOWN in the combined service while valid API log rates
remain available. Missing VDOM rates do not invalidate an independently
complete CLI volume total. Volume is available per ADOM, not per VDOM.

The SSH total sums the returned non-excluded CLI rows, which can differ from the
API-visible ADOM set. Per-ADOM volume is attached only to discovered API ADOM
services. An empty SSH scope yields zero daily and average volume. SSH volume
configuration and transport limitations are described in the
[installation guide](installation.md#optional-ssh-log-volume).

Rate levels are disabled by default. When fixed levels are selected, form
prefills are 10,000/20,000 logs/s for upper WARN/CRIT and 10/1 logs/s for lower
WARN/CRIT. Daily volume upper levels are also disabled; their fixed-level
prefill is 20/25 GB/day. Volume thresholds apply to the daily value, not the CLI
average. Configure these in the ADOM or total **log metrics** rule; per-ADOM
rules match the ADOM item. Legacy standalone daily-volume rules remain for old
services but do not configure the combined services.

Individual Resources and standalone Log Volume service registrations remain
loadable for compatibility, with discovery disabled. New installations use the
combined Resources service and ADOM/Total Log Metrics services.
