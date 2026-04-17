#!/bin/bash
# Teste 2 — Coletor sysstat
# Sobe: WAF + Monitor UDP + Cliente + sysstat collector

TOOL="sysstat"
COMPOSE="docker-compose.${TOOL}.yml"
NUM_MESSAGES=${NUM_MESSAGES:-100000}
RUN_ID=${RUN_ID:-1}
WORKERS=${WORKERS:-10}
DURATION=$(( (NUM_MESSAGES / 3500) + 15 )) # estimativa: ~3500 msg/s (10 workers) + 15s margem
SLEEP=$((DURATION + 30))                    # +30s para startup/shutdown dos containers
export NUM_MESSAGES RUN_ID WORKERS DURATION

echo "========================================"
echo "  TCC — Teste com ${TOOL^^}"
echo "  Duração: ${DURATION}s  |  Run: ${RUN_ID}"
echo "========================================"

echo "[1/3] Limpando estado anterior..."
docker compose -f $COMPOSE down --volumes --remove-orphans 2>/dev/null || true
mkdir -p results

echo "[2/3] Build..."
docker compose -f $COMPOSE build

echo "[3/3] Subindo containers..."
docker compose -f $COMPOSE up -d

echo ""
echo "✅ Rodando. Logs: docker compose -f $COMPOSE logs -f sysstat-collector"
echo "⏰ Aguardando ${SLEEP}s (${DURATION}s coleta + 30s buffer)..."
sleep $SLEEP

echo ""
echo "🛑 Parando..."
docker compose -f $COMPOSE down

echo ""
echo "✅ Resultado em: results/sysstat_${NUM_MESSAGES}_run${RUN_ID}_results.json"
cat results/sysstat_${NUM_MESSAGES}_run${RUN_ID}_results.json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(f\"  lat_avg : {d.get('monitor_latency_avg_ms','?')} ms\")
print(f\"  stddev  : {d.get('monitor_latency_stddev_ms','?')} ms\")
print(f\"  amostras: {d.get('monitor_samples','?')}\")
print(f\"  cpu_avg : {d.get('cpu_avg_pct','?')} %\")
print(f\"  mem_avg : {d.get('mem_avg_mb','?')} MB\")
" 2>/dev/null