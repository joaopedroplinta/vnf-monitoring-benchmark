#!/usr/bin/env python3
"""
Comparador — TCC Gerenciamento de Rede

Modos de uso:
  python3 compare.py <N>         Compara as 3 ferramentas para N mensagens
                                 (usa run1). Gera comparison_<N>.csv/.json
  python3 compare.py <N> <RUNS>  Agrega RUNS repetições de N mensagens:
                                 média ± desvio entre runs.
                                 Gera comparison_<N>_<RUNS>runs.csv/.json
  python3 compare.py             Compara as 3 ferramentas em todos os N
                                 disponíveis. Gera comparison_all_runs.csv/.json
"""
import json, csv, os, sys, re, statistics

_results_base = "/app/results" if os.path.exists("/app/results") else os.path.join(os.getcwd(), "results")
_results_sub  = os.environ.get("RESULTS_SUBDIR", "")
RESULTS_DIR   = os.path.join(_results_base, _results_sub) if _results_sub else _results_base
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
    ("collector_cpu_avg_pct",     "CPU média coletor (%)"),
    ("collector_mem_avg_mb",      "Memória média coletor (MB)"),
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
    """Compara as 3 ferramentas para um único valor de N (run 1)."""
    files = {tool: os.path.join(RESULTS_DIR, f"{tool}_{n}_run1_results.json") for tool in TOOLS}
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
        m = re.match(r"ebpf_(\d+)_run\d+_results\.json", fname)
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
            path = os.path.join(RESULTS_DIR, f"{tool}_{n}_run1_results.json")
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

def compare_aggregate(n, num_runs):
    """Agrega múltiplos runs de N mensagens: média ± desvio entre runs."""
    num_runs = int(num_runs)
    agg_metrics = [
        "monitor_latency_avg_ms",
        "monitor_latency_stddev_ms",
        "monitor_latency_max_ms",
        "monitor_latency_min_ms",
        "monitor_samples",
        "cpu_avg_pct",
        "mem_avg_mb",
    ]

    # Pré-carrega todos os arquivos (evita re-leitura e warnings repetidos)
    all_data = {}
    for tool in TOOLS:
        for run_id in range(1, num_runs + 1):
            path = os.path.join(RESULTS_DIR, f"{tool}_{n}_run{run_id}_results.json")
            all_data[(tool, run_id)] = load(path)

    rows = []
    for metric in agg_metrics:
        row = {"metrica": metric}
        for tool in TOOLS:
            values = []
            for run_id in range(1, num_runs + 1):
                data = all_data[(tool, run_id)]
                val = data.get(metric)
                if val != "" and val is not None:
                    values.append(float(val))
            if values:
                mean = round(statistics.mean(values), 4)
                std  = round(statistics.stdev(values), 4) if len(values) > 1 else 0
                row[tool]          = mean
                row[f"{tool}_std"] = std
            else:
                row[tool]          = ""
                row[f"{tool}_std"] = ""
        rows.append(row)

    out_csv  = os.path.join(RESULTS_DIR, f"comparison_{n}_{num_runs}runs.csv")
    out_json = os.path.join(RESULTS_DIR, f"comparison_{n}_{num_runs}runs.json")

    fieldnames = ["metrica"] + [f"{t}{s}" for t in TOOLS for s in ("", "_std")]
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    with open(out_json, "w") as f:
        json.dump({"n_messages": n, "num_runs": num_runs, "tools": TOOLS,
                   "metrics": agg_metrics, "data": rows}, f, indent=2)

    print(f"\n📊 Agregação — {n} msgs × {num_runs} runs:\n")
    header = f"{'métrica':<35} {'eBPF mean±std':>18} {'sysstat mean±std':>18} {'prom mean±std':>18}"
    print(header)
    print("-" * len(header))
    for row in rows:
        def fmt(t):
            m, s = row.get(t, ""), row.get(f"{t}_std", "")
            return f"{m}±{s}" if m != "" else "-"
        print(f"{row['metrica']:<35} {fmt('ebpf'):>18} {fmt('sysstat'):>18} {fmt('prometheus'):>18}")
    print(f"\n✅ Salvo em {out_csv} e {out_json}")


def main():
    if len(sys.argv) == 3:
        compare_aggregate(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        compare_single(sys.argv[1])
    else:
        compare_all_runs()

if __name__ == "__main__":
    main()
