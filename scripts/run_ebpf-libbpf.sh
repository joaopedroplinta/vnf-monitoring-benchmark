#!/bin/bash
# Executa benchmark eBPF (libbpf) — variante sem BCC/LLVM no processo observador.
# Uso: NUM_MESSAGES=100000 bash scripts/run_ebpf_libbpf.sh
set -euo pipefail

NUM_MESSAGES="${NUM_MESSAGES:-100000}"
RUN_ID="${RUN_ID:-1}"
WORKERS="${WORKERS:-10}"
COMPOSE_FILE="docker-compose.ebpf-libbpf.yml"

if ! [[ "$NUM_MESSAGES" =~ ^[1-9][0-9]*$ ]]; then
    echo "Erro: NUM_MESSAGES inválido: '$NUM_MESSAGES'" >&2
    exit 1
fi

PAYLOADS_FILE_HOST="${PAYLOADS_FILE_HOST:-data/payloads/payloads_${NUM_MESSAGES}_6040.bin}"
if [ ! -f "$PAYLOADS_FILE_HOST" ]; then
    echo "Erro: arquivo de payloads não encontrado: $PAYLOADS_FILE_HOST" >&2
    echo "  Execute: python3 scripts/gen_payloads.py $NUM_MESSAGES" >&2
    exit 1
fi

DURATION=$(( NUM_MESSAGES / 3500 + 15 ))
PAYLOADS_FILE="/app/payloads/payloads_${NUM_MESSAGES}_6040.bin"
RESULT_FILE="results/ebpf_${NUM_MESSAGES}_run${RUN_ID}_results.json"

echo "=== eBPF-libbpf | N=$NUM_MESSAGES | run=$RUN_ID | duration=${DURATION}s ==="

export NUM_MESSAGES DURATION RUN_ID WORKERS PAYLOADS_FILE

if [ "${SKIP_BUILD:-0}" != "1" ]; then
    docker compose -f "$COMPOSE_FILE" build
fi

docker compose -f "$COMPOSE_FILE" up -d waf observador client

echo "Aguardando probe finalizar..."
docker compose -f "$COMPOSE_FILE" run --rm \
    -e COLLECTOR=ebpf \
    -e RESULTS_PATH="/app/results/ebpf_${NUM_MESSAGES}_run${RUN_ID}_results.json" \
    -e DURATION="$DURATION" \
    ebpf-collector

docker logs observador 2>&1 | tail -5 > /tmp/collector_last_logs.txt || true
docker compose -f "$COMPOSE_FILE" down --remove-orphans

if [ -f "$RESULT_FILE" ]; then
    echo ""
    echo "=== Resultado ==="
    python3 -c "
import json
with open('$RESULT_FILE') as f:
    d = json.load(f)
print(f\"  lat_avg={d['observador_latency_avg_ms']}ms | samples={d['observador_samples']} | mem={d['collector_mem_avg_mb']}MB | cpu={d['collector_cpu_avg_pct']}%\")
"
else
    echo "Erro: arquivo de resultado não encontrado: $RESULT_FILE" >&2
    cat /tmp/collector_last_logs.txt >&2
    exit 1
fi
