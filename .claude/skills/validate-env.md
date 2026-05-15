---
description: Validates the environment before running experiments — checks Docker availability, kernel headers for eBPF, BCC installation, required ports, and Docker Compose files. Usage: /validate-env
---

The user wants to verify the environment is ready to run TCC experiments.

Run all checks using Bash and report each with ✅ / ⚠️ / ❌:

### Docker checks
```bash
docker info --format '{{.ServerVersion}}'   # ✅ if returns version
docker compose version                       # ✅ if returns version
```

### Port availability
```bash
ss -tulpn | grep -E ':8080|:9999|:8000'
```
- ✅ if ports are free
- ❌ if occupied — show which process is using them and suggest `docker compose down`

### eBPF / kernel checks
```bash
uname -r                                     # kernel version
ls /sys/kernel/debug/tracing/ 2>/dev/null   # eBPF tracing available
ls /lib/modules/$(uname -r)/ 2>/dev/null   # kernel headers present
python3 -c "from bcc import BPF; print('BCC OK')" 2>/dev/null  # BCC available
```
- Warn if running in WSL2: `uname -r | grep -i microsoft`
- eBPF latency will be 0 in WSL2 (kretprobe limitation) — expected, not a bug

### Results directory
```bash
ls -la results/
```
- Show which result files already exist and their sizes
- Warn if results are from a previous run and may be outdated

### Docker Compose files
- Verify these files exist: `docker-compose.ebpf.yml`, `docker-compose.sysstat.yml`, `docker-compose.prometheus.yml`
- Verify `configs/Dockerfile` and `configs/Dockerfile.client` exist

### Summary
End with a go/no-go summary:
- ✅ **Pronto para rodar** — all critical checks passed
- ⚠️ **Pronto com ressalvas** — non-critical issues (e.g., eBPF latency limitation in WSL2)
- ❌ **Não pronto** — list blocking issues that must be fixed first
