#!/bin/bash
set -euo pipefail
# Teste 2 — Coletor sysstat
# Sobe: WAF + Observador UDP + Cliente + sysstat collector

TOOL="sysstat"
COMPOSE="docker-compose.${TOOL}.yml"
NUM_MESSAGES=${NUM_MESSAGES:-100000}
if ! [[ "${NUM_MESSAGES}" =~ ^[1-9][0-9]*$ ]]; then
    echo "❌ NUM_MESSAGES deve ser um inteiro positivo (atual: '${NUM_MESSAGES}')"
    exit 1
fi
RUN_ID=${RUN_ID:-1}
WORKERS=${WORKERS:-10}
DURATION=$(( (NUM_MESSAGES / 8000) + 20 )) # estimativa: ~8000 msg/s (asyncio + 200 workers) + 20s margem
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
if [ "${SKIP_BUILD:-0}" != "1" ]; then
    docker compose -f $COMPOSE build
else
    echo "  (pulando build — SKIP_BUILD=1)"
fi

echo "[3/3] Subindo containers..."
docker compose -f $COMPOSE up -d

echo ""
echo "✅ Rodando. Logs: docker compose -f $COMPOSE logs -f sysstat-collector"
echo "⏰ Aguardando coletor finalizar (DURATION=${DURATION}s, timeout=${SLEEP}s)..."
docker wait sysstat-collector 2>/dev/null || sleep $SLEEP

echo ""
RESULTS_HOST_DIR="results${RESULTS_SUBDIR:+/${RESULTS_SUBDIR}}"
RESULT_FILE="${RESULTS_HOST_DIR}/sysstat_${NUM_MESSAGES}_run${RUN_ID}_results.json"

echo "🛑 Parando..."
docker compose -f $COMPOSE logs sysstat-collector 2>/dev/null > /tmp/collector_last_logs.txt || true
docker compose -f $COMPOSE down

echo ""
if [ -f "$RESULT_FILE" ]; then
    echo "✅ Resultado em: ${RESULT_FILE}"
    python3 -c "
import json
d=json.load(open('${RESULT_FILE}'))
print(f\"  lat_avg : {d.get('observador_latency_avg_ms','?')} ms\")
print(f\"  stddev  : {d.get('observador_latency_stddev_ms','?')} ms\")
print(f\"  amostras: {d.get('observador_samples','?')}\")
print(f\"  cpu_avg : {d.get('cpu_avg_pct','?')} %\")
print(f\"  mem_avg : {d.get('mem_avg_mb','?')} MB\")
"
else
    echo "❌ Resultado NÃO encontrado: ${RESULT_FILE}"
    echo "   Últimos logs do coletor:"
    tail -30 /tmp/collector_last_logs.txt 2>/dev/null || echo "   (sem logs)"
fi