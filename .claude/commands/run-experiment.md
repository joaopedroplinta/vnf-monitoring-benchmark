---
description: Runs a single monitoring experiment. Usage: /run-experiment <tool> where tool is ebpf, sysstat, or prometheus. Optionally pass duration in seconds: /run-experiment ebpf 60
---

The user wants to run a single experiment. Extract the tool name and optional duration from the arguments.

Valid tools: `ebpf`, `sysstat`, `prometheus`
Default duration: 300 seconds

Steps:
1. Validate the tool argument. If missing or invalid, ask the user which tool to run.
2. Use the experiment-orchestrator agent to run the experiment for the specified tool with the given duration.
3. After completion, show the summary from the results JSON.

If the tool is `ebpf`, warn the user that eBPF requires Docker privileged mode and that latency may appear as 0ms in WSL2 — this is expected behavior documented in GEMINI.md.
