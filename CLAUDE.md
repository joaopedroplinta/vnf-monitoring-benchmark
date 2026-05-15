# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Academic thesis (TCC) benchmarking three Linux network monitoring approaches around a simplified WAF (Web Application Firewall). The core question: what is the overhead of eBPF-based monitoring vs. userspace alternatives?

**Tools compared:** eBPF (libbpf+CO-RE), Sysstat (`/proc/net/dev` + psutil), Prometheus (sysstat + HTTP endpoint)

## Running Tests

### Step 1 — Generate payloads (once, before any test)

```bash
python3 scripts/gen_payloads.py 100000   # → data/payloads/payloads_100000_6040.bin
python3 scripts/gen_payloads.py 500000
python3 scripts/gen_payloads.py 1000000
python3 scripts/gen_payloads.py 2000000
```

### Step 2 — Run benchmarks

Each script orchestrates a full test cycle (build → run → collect → stop):

```bash
NUM_MESSAGES=100000 bash scripts/run_ebpf.sh
NUM_MESSAGES=100000 bash scripts/run_sysstat.sh
NUM_MESSAGES=100000 bash scripts/run_prometheus.sh
```

Run multiple repetitions of a single tool:
```bash
bash scripts/run_multi.sh <tool> <num_messages> <num_runs>
# Exemplo: bash scripts/run_multi.sh ebpf 100000 30
# Executa N runs, exporta RUN_ID=1..N, chama compare.py ao final
# Use --pre para salvar em results/pre_testes/ (testes preliminares)
# Suporta: ebpf | sysstat | prometheus | ebpf-libbpf
```

Aggregate results after running tests:
```bash
python3 src/compare.py <N>        # → results/comparison_<N>.csv/.json
python3 src/compare.py <N> <RUNS> # → results/comparison_<N>_<RUNS>runs.csv/.json (média ± IC95%)
python3 src/compare.py            # → results/comparison_all_runs.csv/.json
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NUM_MESSAGES` | 100000 | Used for DURATION calculation and result file naming |
| `DURATION` | `NUM_MESSAGES/8000 + 20` | How long collectors run (seconds) |
| `RUN_ID` | 1 | Run identifier appended to result filenames |
| `WORKERS` | 200 | Concurrent asyncio coroutines in client (persistent connections) |
| `QUEUE_SIZE` | 2000 | Client payload queue size — controls RAM usage (O(QUEUE_SIZE), not O(N)) |
| `PAYLOADS_FILE` | `/app/payloads/payloads_<N>_6040.bin` | Path to payload file inside client container |
| `PAYLOADS_FILE_HOST` | `data/payloads/payloads_<N>_6040.bin` | Override payload file path on host |
| `WAF_METRICS_PATH` | `/app/results/waf_metrics.json` | Shared file where WAF writes inspection timing stats |
| `WAF_INSPECT_WORKERS` | `os.cpu_count()` | ThreadPoolExecutor workers for WAF inspection |

## Architecture

Three independent Docker Compose stacks share the same topology:

```
Client → WAF (TCP :8080) → Observador (UDP :9999)
                                  ↑
                            probe.py (1 req/s)
```

**Traffic flow:**
1. `src/client/client.py` streams pre-generated payloads from `PAYLOADS_FILE` via asyncio queue (lazy loading — constant RAM regardless of N) and sends to WAF on port 8080 using 200 persistent connections with 4-byte framing
2. WAF (`src/vnf/waf.py`) inspects for SQLi, XSS, Path Traversal, RCE, Null Byte attacks using asyncio + ThreadPoolExecutor; writes inspection timing to `waf_metrics.json` every 100 requests
3. Observador (`src/vnf/observador_*.py`) reads `waf_metrics.json` and serves UDP probes on :9999 with a JSON of metrics (bytes RX/TX, CPU/mem, inspect stats)
4. `src/probe.py` sends UDP probes every 1s, measuring roundtrip latency as the primary overhead metric

**Payload protocol (WAF ↔ Client):**
```
Request:  [4 bytes big-endian: payload length] + [payload bytes]
Response: "ALLOWED:OK\n" or "BLOCKED:<reason>\n"
```
Connection is persistent — multiple messages per TCP connection.

**Observador implementations:**
- `src/vnf/observador_ebpf.py` — BCC kprobes on `tcp_sendmsg` / `tcp_cleanup_rbuf` (sport=8080); requires privileged container + BPF filesystem
- `src/vnf/observador_ebpf_libbpf.py` — libbpf+CO-RE variant (compiled by `ebpf_entrypoint.sh`); ~15 MB RSS vs ~196 MB for BCC
- `src/vnf/observador_sysstat.py` — polls `/proc/net/dev` (interface `lo`) in userspace
- `src/vnf/observador_prometheus.py` — same as sysstat + HTTP metrics endpoint on port 8000

**Key ports:** TCP 8080 (WAF), UDP 9999 (observador telemetry), HTTP 8000 (Prometheus only)

## Docker Setup Details

- `configs/Dockerfile` — Ubuntu 24.04, BCC tools, Python 3, psutil, prometheus_client
- `configs/Dockerfile.client` — Lightweight Python 3.9 slim
- `configs/Dockerfile.ebpf-libbpf` — Ubuntu 24.04 with libbpf1, clang, bpftool (no BCC/LLVM)
- eBPF compose requires: `privileged: true`, `pid: host`, BPF filesystem mounts, `/sys/kernel/btf`
- sysstat/Prometheus composes are unprivileged with `pid: host` for psutil process tracking
- Client container mounts `./data/payloads:/app/payloads:ro` — payload files must exist before running

## Output

Result files follow the pattern `results/<tool>_<N>_run<RUN_ID>_results.json`.

| Directory | Purpose |
|---|---|
| `results/` | Official TCC results (30 runs per tool per N) |
| `results/pre_testes/` | Preliminary/validation runs (use `--pre` flag) |

`data/payloads/` is gitignored — generate before running tests.

| Output file | When generated |
|---|---|
| `comparison_<N>.csv/.json` | `compare.py <N>` — single N, run1 |
| `comparison_<N>_<RUNS>runs.csv/.json` | `compare.py <N> <RUNS>` — mean ± IC95% across runs |
| `comparison_all_runs.csv/.json` | `compare.py` (no args) — all N values found in results/ |

Key fields in each result JSON:

| Field | Description |
|---|---|
| `observador_latency_avg_ms` | Mean roundtrip UDP latency (primary overhead metric) |
| `observador_samples` | Number of probe samples collected |
| `cpu_avg_pct` / `mem_avg_mb` | WAF process CPU and memory (via psutil) |
| `collector_cpu_avg_pct` / `collector_mem_avg_mb` | Observador process CPU and memory |
| `inspect_count` | Total payloads inspected by WAF |
| `inspect_avg_ms` | Mean WAF inspection time per payload |
| `inspect_min_ms` / `inspect_max_ms` | Min/max WAF inspection time |

## Claude Code Agents & Skills

This project has custom agents (`.claude/agents/`) and slash commands (`.claude/commands/`):

| Agent | Purpose |
|---|---|
| `experiment-orchestrator` | Runs full test battery via docker compose |
| `results-analyst` | Statistical analysis of result JSONs |
| `ebpf-specialist` | eBPF/BCC/kprobe debugging |
| `docker-debugger` | Container and networking issues |
| `anomaly-investigator` | Detects anomalies in collected data |
| `tcc-writer` | Generates academic Portuguese text from results |
| `metrics-comparator` | Dimension-by-dimension tool comparison with verdicts |
| `sysstat-specialist` | `/proc/net/dev` parsing, psutil tracking, WAF metrics debugging |
| `prometheus-specialist` | Prometheus HTTP endpoint, Gauge anomalies, port 8000 conflicts |

| Command | Usage |
|---|---|
| `/validate-env` | Check Docker, kernel, ports before running |
| `/run-experiment <tool>` | Run a single collector |
| `/run-all [duration]` | Run all three in sequence |
| `/check-results` | Quick summary of current result JSONs |
| `/generate-report` | Run compare.py and format output |
| `/analyze-anomalies` | Deep anomaly investigation |
| `/write-section <section>` | Generate TCC academic section |

## Current Status (14/05/2026)

- Official results collected: N=100k, 500k, 1M — 30 runs each (notebook i5 11th gen + BigLinux)
- N=100k also re-collected with libbpf in `feat/ebpf-libbpf-memory` branch
- **Pending:** merge `feat/ebpf-libbpf-memory` → main, then re-collect all data on desktop AMD Ryzen 5 5500 (Ubuntu native) for thermal consistency
- **Next N:** 2M messages
- **Runs per N:** 30 (fixed by advisor)
