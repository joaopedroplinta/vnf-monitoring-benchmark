---
description: Runs a deep anomaly investigation on the current experiment results, distinguishing expected WSL2/Docker artifacts from real data problems. Usage: /analyze-anomalies
---

The user wants a thorough anomaly investigation of the current results.

Steps:
1. Use the anomaly-investigator agent to read all result files and perform the full analysis.
2. The agent will:
   - Identify each metric that has a suspicious value
   - Label it as EXPECTED / ANOMALY / CRITICAL
   - Explain the root cause for each finding
   - Suggest remediation for genuine anomalies
3. After the agent completes, ask the user if they want to:
   - Fix any issues and re-run the affected experiment (`/run-experiment <tool>`)
   - Get academic text explaining the anomalies (`/write-section discussao`)
   - See the full competitive comparison (`/generate-report`)
