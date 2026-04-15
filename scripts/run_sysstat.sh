#!/bin/bash
# Teste 2 — Coletor sysstat
# Sobe: WAF + Monitor UDP + Cliente + sysstat collector

TOOL="sysstat"
COMPOSE="docker-compose.${TOOL}.yml"
NUM_MESSAGES=100
DURATION=$((NUM_MESSAGES))        # coletores rodam exatamente o tempo do cliente
SLEEP=$((DURATION + 30))          # script espera +30s de buffer para startup e overhead
export NUM_MESSAGES DURATION

echo "========================================"
echo "  TCC — Teste com ${TOOL^^}"
echo "  Duração: ${DURATION}s"
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
echo "✅ Resultado em: results/sysstat_results.json"
cat results/sysstat_results.json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(f\"  lat_avg : {d.get('monitor_latency_avg_ms','?')} ms\")
print(f\"  stddev  : {d.get('monitor_latency_stddev_ms','?')} ms\")
print(f\"  amostras: {d.get('monitor_samples','?')}\")
print(f\"  cpu_avg : {d.get('cpu_avg_pct','?')} %\")
print(f\"  mem_avg : {d.get('mem_avg_mb','?')} MB\")
" 2>/dev/null