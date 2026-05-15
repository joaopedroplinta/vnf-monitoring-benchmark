---
description: Shows a quick summary of the current experiment results from all three JSON files. Displays key metrics side-by-side without running any experiments. Usage: /check-results
---

The user wants to see the current state of their experiment results.

Steps:
1. Read these files if they exist:
   - `results/ebpf_results.json`
   - `results/sysstat_results.json`
   - `results/prometheus_results.json`
   - `results/comparison.json`

2. Display a compact side-by-side table with the most important metrics:
   - `monitor_latency_avg_ms`
   - `monitor_latency_stddev_ms`
   - `monitor_samples`
   - `cpu_avg_pct`
   - `bytes_rx` / `bytes_tx`
   - `waf_blocked`
   - `duration_s`

3. For each file that is missing, show a clear warning: "❌ <tool>_results.json não encontrado — rode /run-experiment <tool>"

4. If `comparison.json` exists, also show when it was last generated (use file modification time via Bash if needed).

5. Flag any obvious anomalies: zero latency in eBPF (expected), missing values, or tool disagreement on `waf_blocked`.

Keep the output concise — this is a quick status check, not a deep analysis. For deep analysis, use /analyze-anomalies or invoke the results-analyst agent.
