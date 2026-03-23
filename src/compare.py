#!/usr/bin/python3
"""
Comparador de Coletores — TCC Gerenciamento de Rede
Lê os resultados dos 3 coletores e gera comparison.csv
"""

import os, json, csv
from datetime import datetime

RESULTS = {
    "ebpf":       "/app/results/ebpf_results.json",
    "sysstat":    "/app/results/sysstat_results.json",
    "prometheus": "/app/results/prometheus_results.json",
}
CSV_PATH  = "/app/results/comparison.csv"
JSON_PATH = "/app/results/comparison.json"

METRICS = [
    "connections",
    "bytes_tx",
    "bytes_rx",
    "latency_avg_ms",
    "latency_max_ms",
    "latency_min_ms",
    "cpu_avg_pct",
    "mem_avg_mb",
    "duration_s",
]

def load(path):
    if not os.path.exists(path):
        print(f"  ⚠️  Arquivo não encontrado: {path}")
        return None
    with open(path) as f:
        return json.load(f)

def compare():
    print("=" * 65)
    print("  📊 Comparação dos Coletores — eBPF · sysstat · Prometheus")
    print("=" * 65)

    results = {}
    for name, path in RESULTS.items():
        data = load(path)
        if data:
            results[name] = data
            print(f"  ✅ {name:<12} carregado ({data.get('timestamp','')})")
        else:
            results[name] = {}

    if not results:
        print("  ❌ Nenhum resultado encontrado. Rode os coletores primeiro.")
        return

    # ── Tabela no terminal ────────────────────────────────────────────────────
    col_w = 18
    print("\n" + "-" * 65)
    header = f"  {'Métrica':<22}" + "".join(f"{k:>{col_w}}" for k in results)
    print(header)
    print("-" * 65)

    for metric in METRICS:
        row = f"  {metric:<22}"
        for name in results:
            val = results[name].get(metric, "N/A")
            row += f"{str(val):>{col_w}}"
        print(row)

    print("-" * 65)

    # ── Diferenças relativas entre coletores ─────────────────────────────────
    collectors = list(results.keys())
    if len(collectors) >= 2:
        print("\n  📐 Diferença relativa entre coletores:")
        for metric in ["latency_avg_ms", "cpu_avg_pct", "mem_avg_mb"]:
            vals = {c: results[c].get(metric) for c in collectors
                    if results[c].get(metric) not in (None, 0, "N/A")}
            if len(vals) >= 2:
                items = list(vals.items())
                for i in range(len(items)):
                    for j in range(i+1, len(items)):
                        ca, va = items[i]
                        cb, vb = items[j]
                        try:
                            diff = abs(va - vb) / ((va + vb) / 2) * 100
                            print(f"    {metric:<22} {ca} vs {cb}: {diff:.1f}% de diferença")
                        except ZeroDivisionError:
                            pass

    # ── Salva CSV ─────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metrica"] + list(results.keys()))
        for metric in METRICS:
            row = [metric] + [results[c].get(metric, "") for c in results]
            writer.writerow(row)

    # ── Salva JSON ────────────────────────────────────────────────────────────
    comparison = {
        "generated_at": datetime.utcnow().isoformat(),
        "collectors":   results,
        "summary": {
            metric: {c: results[c].get(metric) for c in results}
            for metric in METRICS
        }
    }
    with open(JSON_PATH, "w") as f:
        json.dump(comparison, f, indent=2)

    print(f"\n  💾 CSV  salvo: {CSV_PATH}")
    print(f"  💾 JSON salvo: {JSON_PATH}")
    print("=" * 65)

if __name__ == "__main__":
    compare()
