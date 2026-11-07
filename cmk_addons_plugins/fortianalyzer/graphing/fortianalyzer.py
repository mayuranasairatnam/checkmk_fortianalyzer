"""
FortiAnalyzer metric and graph definitions.

Generic license metrics and devices deliberately use Checkmk's automatic
rendering (or the installed FortiManager definitions), avoiding duplicate
global metric names when both packages are installed.
"""
from cmk.graphing.v1 import Title
from cmk.graphing.v1.metrics import AutoPrecision, Color, DecimalNotation, IECNotation, Metric, StrictPrecision, Unit
from cmk.graphing.v1.graphs import Graph, MinimalRange
from cmk.graphing.v1.perfometers import Closed, FocusRange, Perfometer

COUNT = Unit(DecimalNotation(''), StrictPrecision(0))
PERCENT = Unit(DecimalNotation('%'), AutoPrecision(1))
BYTES = Unit(IECNotation('B'), AutoPrecision(2))
RATE = Unit(DecimalNotation('logs/s'), AutoPrecision(2))
DAYS = Unit(DecimalNotation('days'), StrictPrecision(0))

metric_faz_max_adoms = Metric(name='faz_max_adoms', title=Title('Maximum ADOMs'), unit=COUNT, color=Color.BLUE)
metric_faz_logging_devices = Metric(name='faz_logging_devices', title=Title('FortiGates / Logging Devices'), unit=COUNT, color=Color.BLUE)
metric_logs_per_second = Metric(name='logs_per_second', title=Title('Log rate'), unit=RATE, color=Color.BLUE)
metric_faz_reported_logs_per_second = Metric(name='faz_reported_logs_per_second', title=Title('Reported log rate (incomplete coverage)'), unit=RATE, color=Color.ORANGE)
metric_vdoms = Metric(name='vdoms', title=Title('VDOMs'), unit=COUNT, color=Color.GREEN)
metric_faz_support_days = Metric(name='faz_support_days', title=Title('Remaining support lifetime'), unit=DAYS, color=Color.ORANGE)
metric_faz_cpu_percent = Metric(name='faz_cpu_percent', title=Title('CPU average'), unit=PERCENT, color=Color.BLUE)
metric_faz_disk_percent = Metric(name='faz_disk_percent', title=Title('Disk usage'), unit=PERCENT, color=Color.GREEN)
metric_faz_memory_percent = Metric(name='faz_memory_percent', title=Title('Memory usage'), unit=PERCENT, color=Color.PURPLE)
metric_faz_memory_used = Metric(name='faz_memory_used', title=Title('Memory used'), unit=BYTES, color=Color.BLUE)
metric_faz_memory_total = Metric(name='faz_memory_total', title=Title('Memory total'), unit=BYTES, color=Color.GREEN)
metric_faz_memory_free = Metric(name='faz_memory_free', title=Title('Memory free'), unit=BYTES, color=Color.CYAN)

graph_fortianalyzer_license = Graph(name='fortianalyzer_license', title=Title('FortiAnalyzer device licenses'),
    simple_lines=['used_devices', 'licensed_devices', 'free_devices'])
graph_fortianalyzer_lograte = Graph(name='fortianalyzer_lograte', title=Title('FortiAnalyzer log rate'),
    simple_lines=['logs_per_second'])
graph_fortianalyzer_reported_lograte = Graph(name='fortianalyzer_reported_lograte', title=Title('FortiAnalyzer reported log rate (incomplete coverage)'),
    simple_lines=['faz_reported_logs_per_second'])
graph_fortianalyzer_adom_counts = Graph(name='fortianalyzer_adom_counts', title=Title('FortiAnalyzer ADOM devices and VDOMs'),
    simple_lines=['devices', 'vdoms'])
graph_fortianalyzer_cpu = Graph(name='fortianalyzer_cpu', title=Title('FortiAnalyzer CPU average'), simple_lines=['faz_cpu_percent'], minimal_range=MinimalRange(0, 100))
graph_fortianalyzer_disk = Graph(name='fortianalyzer_disk', title=Title('FortiAnalyzer disk usage'), simple_lines=['faz_disk_percent'], minimal_range=MinimalRange(0, 100))
graph_fortianalyzer_memory_percent = Graph(name='fortianalyzer_memory_percent', title=Title('FortiAnalyzer memory usage'), simple_lines=['faz_memory_percent'], minimal_range=MinimalRange(0, 100))
graph_fortianalyzer_memory_used = Graph(name='fortianalyzer_memory_used', title=Title('FortiAnalyzer memory used'), simple_lines=['faz_memory_used'])
graph_fortianalyzer_memory_total = Graph(name='fortianalyzer_memory_total', title=Title('FortiAnalyzer memory total'), simple_lines=['faz_memory_total'])
graph_fortianalyzer_memory_free = Graph(name='fortianalyzer_memory_free', title=Title('FortiAnalyzer memory free'), simple_lines=['faz_memory_free'])
perfometer_fortianalyzer_license = Perfometer(name='fortianalyzer_license',
    focus_range=FocusRange(Closed(0), Closed(100)), segments=['utilization_percent'])

# Single-metric graphs also work when other API measurements are unavailable.
graph_fortianalyzer_license_utilization = Graph(name='fortianalyzer_license_utilization', title=Title('FortiAnalyzer Device license utilization'),
    simple_lines=['utilization_percent'], minimal_range=MinimalRange(0, 100))
graph_fortianalyzer_max_adoms = Graph(name='fortianalyzer_max_adoms', title=Title('FortiAnalyzer Maximum ADOMs'),
    simple_lines=['faz_max_adoms'])
graph_fortianalyzer_managed = Graph(name='fortianalyzer_managed', title=Title('FortiAnalyzer FortiGates / Logging Devices'),
    simple_lines=['faz_logging_devices'])
graph_fortianalyzer_support = Graph(name='fortianalyzer_support', title=Title('FortiAnalyzer Remaining support lifetime'),
    simple_lines=['faz_support_days'])
graph_fortianalyzer_adom_devices = Graph(name='fortianalyzer_adom_devices', title=Title('FortiAnalyzer ADOM devices'),
    simple_lines=['devices'])
graph_fortianalyzer_vdoms = Graph(name='fortianalyzer_vdoms', title=Title('FortiAnalyzer ADOM VDOMs'),
    simple_lines=['vdoms'])

VOLUME = Unit(DecimalNotation('GB/day'), AutoPrecision(3))
metric_faz_log_gb_day = Metric(name='faz_log_gb_day', title=Title('Daily log volume'), unit=VOLUME, color=Color.BLUE)
metric_faz_log_average_gb_day = Metric(name='faz_log_average_gb_day', title=Title('CLI average daily log volume'), unit=VOLUME, color=Color.GREEN)
graph_fortianalyzer_logvolume = Graph(name='fortianalyzer_logvolume', title=Title('FortiAnalyzer daily log volume'),
    simple_lines=['faz_log_gb_day'])
graph_fortianalyzer_logvolume_average = Graph(name='fortianalyzer_logvolume_average', title=Title('FortiAnalyzer average daily log volume'),
    simple_lines=['faz_log_average_gb_day'])

# Combined Resources service: retain individual graphs and add overviews.
graph_fortianalyzer_resources = Graph(name='fortianalyzer_resources', title=Title('FortiAnalyzer utilization'),
    simple_lines=['faz_cpu_percent', 'faz_memory_percent', 'faz_disk_percent'], minimal_range=MinimalRange(0, 100))
graph_fortianalyzer_memory = Graph(name='fortianalyzer_memory', title=Title('FortiAnalyzer memory'),
    simple_lines=['faz_memory_used', 'faz_memory_total', 'faz_memory_free'])
