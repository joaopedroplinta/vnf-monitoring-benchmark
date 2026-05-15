---
description: Runs compare.py to regenerate comparison.json and comparison.csv, then displays the formatted comparison table. Usage: /generate-report
---

The user wants to regenerate the comparison report from existing result files.

Steps:
1. Check that at least one of the result JSON files exists in `results/`. If none exist, tell the user to run `/run-all` first.
2. Run the comparison script:
   ```bash
   python3 src/compare.py
   ```
3. Display the contents of `results/comparison.csv` as a formatted markdown table.
4. Highlight the winner in each metric row (lowest latency, lowest CPU, highest samples).
5. Mention any missing result files that prevented full comparison.
6. Suggest next steps: "Para análise aprofundada use /analyze-anomalies. Para texto acadêmico use /write-section resultados."
