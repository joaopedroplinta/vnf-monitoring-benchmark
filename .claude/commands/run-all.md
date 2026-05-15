---
description: Runs the full TCC experiment battery — eBPF, Sysstat, and Prometheus — in sequence, then generates the comparison report. Takes approximately 15-20 minutes total. Usage: /run-all or /run-all 60 (for a quick 60s test per tool).
---

The user wants to run all three experiments in sequence. This is the full TCC test battery.

Steps:
1. Warn the user this will take approximately 15-20 minutes (3 × 300s + build time) or less if a custom duration was provided.
2. Ask for confirmation before proceeding.
3. Use the experiment-orchestrator agent to:
   a. Run eBPF experiment (with the specified or default duration)
   b. Run Sysstat experiment
   c. Run Prometheus experiment
   d. Run `python3 src/compare.py` to generate comparison.json and comparison.csv
4. After all experiments complete, invoke the metrics-comparator agent to show a structured comparison of the results.

If the user passed a duration argument (e.g., `/run-all 60`), pass that duration to each experiment.

Always show progress as each experiment completes, not just at the end.
