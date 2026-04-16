#!/usr/bin/env python3
"""
Comparador — TCC Gerenciamento de Rede

Modos de uso:
  python3 compare.py <N>   Compara as 3 ferramentas para N mensagens.
                           Gera comparison_<N>.csv e comparison_<N>.json
  python3 compare.py       Compara as 3 ferramentas em todos os runs
                           disponíveis em results/. Gera
                           comparison_all_runs.csv e comparison_all_runs.json
"""
import json, csv, os, sys, re

RESULTS_DIR = "/app/results" if os.path.exists("/app/results") else os.path.join(os.getcwd(), "results")
TOOLS       = ["ebpf", "sysstat", "prometheus"]

METRICS = [
    ("monitor_latency_avg_ms",    "Latência média (ms)"),
    ("monitor_latency_stddev_ms", "Desvio padrão (ms)"),
    ("monitor_latency_max_ms",    "Latência máx (ms)"),
    ("monitor_latency_min_ms",    "Latência mín (ms)"),
    ("monitor_samples",           "Amostras coletadas"),
    ("bytes_rx",                  "Bytes RX WAF"),
    ("bytes_tx",                  "Bytes TX WAF"),
    ("cpu_avg_pct",               "CPU média WAF (%)"),
    ("mem_avg_mb",                "Memória média WAF (MB)"),
    ("duration_s",                "Duração (s)"),
]

def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Não foi possível ler {path}: {e}")
        return {}

def compare_single(n):
    """Compara as 3 ferramentas para um único valor de N."""
    files = {tool: os.path.join(RESULTS_DIR, f"{tool}_{n}_results.json") for tool in TOOLS}
    data  = {tool: load(path) for tool, path in files.items()}

    rows = []
    for key, label in METRICS:
        row = {"metrica": key}
        for tool in TOOLS:
            row[tool] = data[tool].get(key, "")
        rows.append(row)

    out_csv  = os.path.join(RESULTS_DIR, f"comparison_{n}.csv")
    out_json = os.path.join(RESULTS_DIR, f"comparison_{n}.json")

    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metrica"] + TOOLS)
        w.writeheader()
        w.writerows(rows)

    with open(out_json, "w") as f:
        json.dump({"n_messages": n, "tools": TOOLS, "metrics": rows, "raw": data}, f, indent=2)

    print(f"\n📊 Comparação — {n} mensagens:\n")
    header = f"{'métrica':<35} {'eBPF':>12} {'sysstat':>12} {'prometheus':>12}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(f"{row['metrica']:<35} {str(row.get('ebpf','')):>12} "
              f"{str(row.get('sysstat','')):>12} {str(row.get('prometheus','')):>12}")
    print(f"\n✅ Salvo em {out_csv} e {out_json}")

def discover_runs():
    """Retorna lista ordenada dos valores de N disponíveis nos results/."""
    ns = set()
    for fname in os.listdir(RESULTS_DIR):
        m = re.match(r"ebpf_(\d+)_results\.json", fname)
        if m:
            ns.add(int(m.group(1)))
    return sorted(ns)

def compare_all_runs():
    """Compara as 3 ferramentas em todos os runs disponíveis."""
    runs = discover_runs()
    if not runs:
        print("⚠️  Nenhum resultado encontrado em results/")
        return

    # Métricas relevantes para comparação cross-run
    cross_metrics = [
        "monitor_latency_avg_ms",
        "monitor_latency_stddev_ms",
        "monitor_latency_max_ms",
        "monitor_samples",
        "cpu_avg_pct",
        "mem_avg_mb",
    ]

    rows = []
    for n in runs:
        row = {"n_messages": n}
        for tool in TOOLS:
            path = os.path.join(RESULTS_DIR, f"{tool}_{n}_results.json")
            data = load(path)
            for metric in cross_metrics:
                row[f"{tool}_{metric}"] = data.get(metric, "")
        rows.append(row)

    fieldnames = ["n_messages"] + [f"{tool}_{m}" for tool in TOOLS for m in cross_metrics]
    out_csv  = os.path.join(RESULTS_DIR, "comparison_all_runs.csv")
    out_json = os.path.join(RESULTS_DIR, "comparison_all_runs.json")

    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    with open(out_json, "w") as f:
        json.dump({"runs": runs, "tools": TOOLS, "metrics": cross_metrics, "data": rows}, f, indent=2)

    print(f"\n📊 Comparação cross-runs ({len(runs)} runs: {runs}):\n")
    header = f"{'N':>6}  {'eBPF avg':>10} {'sys avg':>10} {'prom avg':>10}  {'eBPF std':>10} {'sys std':>10} {'prom std':>10}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['n_messages']:>6}  "
            f"{str(row.get('ebpf_monitor_latency_avg_ms','')):>10} "
            f"{str(row.get('sysstat_monitor_latency_avg_ms','')):>10} "
            f"{str(row.get('prometheus_monitor_latency_avg_ms','')):>10}  "
            f"{str(row.get('ebpf_monitor_latency_stddev_ms','')):>10} "
            f"{str(row.get('sysstat_monitor_latency_stddev_ms','')):>10} "
            f"{str(row.get('prometheus_monitor_latency_stddev_ms','')):>10}"
        )
    print(f"\n✅ Salvo em {out_csv} e {out_json}")

def main():
    if len(sys.argv) > 1:
        compare_single(sys.argv[1])
    else:
        compare_all_runs()

if __name__ == "__main__":
    main()
