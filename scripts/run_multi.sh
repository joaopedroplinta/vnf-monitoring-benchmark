#!/bin/bash
set -euo pipefail
# run_multi.sh — executa múltiplos runs de um coletor
#
# Uso:
#   bash scripts/run_multi.sh <ferramenta> <num_messages> <num_runs>
#
# Exemplos:
#   bash scripts/run_multi.sh ebpf         100000 5
#   bash scripts/run_multi.sh sysstat      100000 5
#   bash scripts/run_multi.sh prometheus   100000 5
TOOL=${1}
NUM_MESSAGES=${2:-100000}
NUM_RUNS=${3:-5}
PRE_ARG="${4:-}"

if [ -z "$TOOL" ]; then
    echo "Uso: bash scripts/run_multi.sh <ebpf|sysstat|prometheus> <num_messages> <num_runs> [--pre]"
    exit 1
fi

if [ ! -f "$(dirname "$0")/run_${TOOL}.sh" ]; then
    echo "Ferramenta inválida: '${TOOL}'. Use ebpf, sysstat ou prometheus."
    exit 1
fi

if [ "$PRE_ARG" = "--pre" ]; then
    export RESULTS_SUBDIR="pre_testes"
else
    export RESULTS_SUBDIR=""
fi

echo "========================================"
echo "  TCC — Múltiplas execuções"
echo "  Ferramenta : ${TOOL}"
echo "  Mensagens  : ${NUM_MESSAGES}"
echo "  Repetições : ${NUM_RUNS}"
[ -n "$RESULTS_SUBDIR" ] && echo "  Destino    : results/${RESULTS_SUBDIR}/" || echo "  Destino    : results/"
echo "========================================"

echo ""
echo "[build] Construindo imagens (uma vez)..."
COMPOSE="docker-compose.${TOOL}.yml"
docker compose -f "$COMPOSE" build
export SKIP_BUILD=1

for i in $(seq 1 $NUM_RUNS); do
    echo ""
    echo "▶ [${TOOL^^}] Execução ${i}/${NUM_RUNS} — ${NUM_MESSAGES} msgs"
    echo "----------------------------------------"
    export NUM_MESSAGES RUN_ID=$i
    bash "$(dirname "$0")/run_${TOOL}.sh"
done

echo ""
echo "========================================"
echo "  ${NUM_RUNS} execuções concluídas!"
echo "  Gerando agregação..."
echo "========================================"

python3 src/compare.py "$NUM_MESSAGES" "$NUM_RUNS"
