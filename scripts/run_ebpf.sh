#!/bin/bash
# Teste 1 — Coletor eBPF
# Sobe: WAF + Observador UDP + Cliente + eBPF collector

TOOL="ebpf"
COMPOSE="docker-compose.${TOOL}.yml"
NUM_MESSAGES=${NUM_MESSAGES:-100000}
RUN_ID=${RUN_ID:-1}
WORKERS=${WORKERS:-10}
DURATION=$(( (NUM_MESSAGES / 3500) + 15 )) # estimativa: ~3500 msg/s (10 workers) + 15s margem
SLEEP=$((DURATION + 30))                    # +30s para startup/shutdown dos containers

# Arquivo de payloads pré-gerado (host → container via volume ./data/payloads:/app/payloads)
_PAYLOADS_HOST="${PAYLOADS_FILE_HOST:-data/payloads/payloads_${NUM_MESSAGES}_6040.bin}"
if [ ! -f "$_PAYLOADS_HOST" ]; then
    echo "❌ Arquivo de payloads não encontrado: $_PAYLOADS_HOST"
    echo "   Gere com: python3 scripts/gen_payloads.py ${NUM_MESSAGES}"
    exit 1
fi
PAYLOADS_FILE="/app/payloads/$(basename $_PAYLOADS_HOST)"

if [ -n "${RESULTS_SUBDIR:-}" ]; then
    RESULTS_PREFIX_CONT="/app/results/${RESULTS_SUBDIR}"
    mkdir -p "results/${RESULTS_SUBDIR}"
else
    RESULTS_PREFIX_CONT="/app/results"
fi
export NUM_MESSAGES RUN_ID WORKERS DURATION PAYLOADS_FILE RESULTS_SUBDIR RESULTS_PREFIX_CONT

echo "========================================"
echo "  TCC — Teste com ${TOOL^^}"
echo "  Duração: ${DURATION}s  |  Run: ${RUN_ID}"
echo "========================================"

echo "[1/3] Limpando estado anterior..."
docker compose -f $COMPOSE down --remove-orphans 2>/dev/null || true
mkdir -p results

echo "[2/3] Build..."
docker compose -f $COMPOSE build

echo "[3/3] Subindo containers..."
docker compose -f $COMPOSE up -d

echo ""
echo "✅ Rodando. Logs: docker compose -f $COMPOSE logs -f ebpf-collector"
echo "⏰ Aguardando coletor finalizar (DURATION=${DURATION}s, timeout=${SLEEP}s)..."
docker wait ebpf-collector 2>/dev/null || sleep $SLEEP

echo ""
echo "🛑 Parando..."
docker compose -f $COMPOSE down

echo ""
RESULTS_HOST_DIR="results${RESULTS_SUBDIR:+/${RESULTS_SUBDIR}}"
echo "✅ Resultado em: ${RESULTS_HOST_DIR}/ebpf_${NUM_MESSAGES}_run${RUN_ID}_results.json"
cat ${RESULTS_HOST_DIR}/ebpf_${NUM_MESSAGES}_run${RUN_ID}_results.json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(f\"  lat_avg : {d.get('observador_latency_avg_ms','?')} ms\")
print(f\"  stddev  : {d.get('observador_latency_stddev_ms','?')} ms\")
print(f\"  amostras: {d.get('observador_samples','?')}\")
print(f\"  cpu_avg : {d.get('cpu_avg_pct','?')} %\")
print(f\"  mem_avg : {d.get('mem_avg_mb','?')} MB\")
" 2>/dev/null