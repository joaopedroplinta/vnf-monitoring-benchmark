#!/bin/bash
# Teste 1 — Coletor eBPF
# Sobe: WAF + Monitor UDP + Cliente + eBPF collector

TOOL="ebpf"
COMPOSE="docker-compose.${TOOL}.yml"
DURATION=300  # 9 min (8 coleta + 1 margem)

echo "========================================"
echo "  TCC — Teste com ${TOOL^^}"
echo "  Duração: 4 minutos"
echo "========================================"

echo "[1/3] Limpando estado anterior..."
docker compose -f $COMPOSE down --volumes --remove-orphans 2>/dev/null || true
mkdir -p results

echo "[2/3] Build..."
docker compose -f $COMPOSE build

echo "[3/3] Subindo containers..."
docker compose -f $COMPOSE up -d

echo ""
echo "✅ Rodando. Logs: docker compose -f $COMPOSE logs -f ebpf-collector"
echo "⏰ Aguardando ${DURATION}s..."
sleep $DURATION

echo ""
echo "🛑 Parando..."
docker compose -f $COMPOSE down

echo ""
echo "✅ Resultado em: results/ebpf_results.json"
cat results/ebpf_results.json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(f\"  lat_avg : {d.get('monitor_latency_avg_ms','?')} ms\")
print(f\"  stddev  : {d.get('monitor_latency_stddev_ms','?')} ms\")
print(f\"  amostras: {d.get('monitor_samples','?')}\")
print(f\"  bloqueados WAF: {d.get('waf_blocked','?')}\")
" 2>/dev/null