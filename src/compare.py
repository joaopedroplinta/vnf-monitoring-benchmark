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
import json, csv, math, os, sys, re, statistics

# t crítico bicaudal 95% (α=0.05) por grau de liberdade (df = n-1)
_T95 = {
    1: 12.706, 2: 4.303,  3: 3.182,  4: 2.776,  5: 2.571,
    6:  2.447, 7: 2.365,  8: 2.306,  9: 2.262, 10: 2.228,
   11:  2.201,12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
   16:  2.120,17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
   21:  2.080,22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
   26:  2.056,27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}

def t_critical(df: int) -> float:
    """t de Student bicaudal 95% para df graus de liberdade."""
    return _T95.get(df, 1.960)  # df > 30 → aproximação normal

_results_base = "/app/results" if os.path.exists("/app/results") else os.path.join(os.getcwd(), "results")
_results_sub  = os.environ.get("RESULTS_SUBDIR", "")
RESULTS_DIR   = os.path.join(_results_base, _results_sub) if _results_sub else _results_base
TOOLS       = ["ebpf", "sysstat", "prometheus"]
TOOL_LABELS = {"ebpf": "eBPF", "sysstat": "sysstat", "prometheus": "Prometheus"}

METRICS = [
    ("observador_latency_avg_ms",    "Latência média (ms)"),
    ("observador_latency_stddev_ms", "Desvio padrão (ms)"),
    ("observador_latency_max_ms",    "Latência máx (ms)"),
    ("observador_latency_min_ms",    "Latência mín (ms)"),
    ("observador_samples",           "Amostras coletadas"),
    ("bytes_rx",                  "Bytes RX WAF"),
    ("bytes_tx",                  "Bytes TX WAF"),
    ("cpu_avg_pct",               "CPU média WAF (%)"),
    ("mem_avg_mb",                "Memória média WAF (MB)"),
    ("collector_cpu_avg_pct",     "CPU média observador (%)"),
    ("collector_mem_avg_mb",      "Memória média observador (MB)"),
    ("duration_s",                "Duração (s)"),
]
METRICS_LABEL = {key: label for key, label in METRICS}

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

    col_tools = [TOOL_LABELS[t] for t in TOOLS]
    rows = []
    for key, label in METRICS:
        row = {"metrica": label}
        for tool in TOOLS:
            row[TOOL_LABELS[tool]] = data[tool].get(key, "")
        rows.append(row)

    out_csv  = os.path.join(RESULTS_DIR, f"comparison_{n}.csv")
    out_json = os.path.join(RESULTS_DIR, f"comparison_{n}.json")

    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metrica"] + col_tools)
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

def discover_ns():
    """Retorna lista ordenada dos valores de N disponíveis nos results/."""
    ns = set()
    for fname in os.listdir(RESULTS_DIR):
        m = re.match(r"ebpf_(\d+)_run\d+_results\.json", fname)
        if m:
            ns.add(int(m.group(1)))
    return sorted(ns)

def discover_num_runs(tool, n):
    """Retorna quantos run files existem para uma dada ferramenta e N."""
    count = 0
    for fname in os.listdir(RESULTS_DIR):
        if re.match(rf"{tool}_{n}_run\d+_results\.json", fname):
            count += 1
    return count

def compare_all_runs():
    """Compara as 3 ferramentas em todos os N disponíveis, usando média de todos os runs."""
    ns = discover_ns()
    if not ns:
        print("⚠️  Nenhum resultado encontrado em results/")
        return

    # Métricas relevantes para comparação cross-N
    cross_metrics = [
        "observador_latency_avg_ms",
        "observador_latency_stddev_ms",
        "observador_latency_max_ms",
        "observador_samples",
        "cpu_avg_pct",
        "mem_avg_mb",
    ]

    rows = []
    for n in ns:
        row = {"n_messages": n}
        for tool in TOOLS:
            num_runs = discover_num_runs(tool, n)
            values = {metric: [] for metric in cross_metrics}
            for run_id in range(1, num_runs + 1):
                path = os.path.join(RESULTS_DIR, f"{tool}_{n}_run{run_id}_results.json")
                data = load(path)
                for metric in cross_metrics:
                    val = data.get(metric)
                    if val != "" and val is not None:
                        values[metric].append(float(val))
            for metric in cross_metrics:
                vals = values[metric]
                row[f"{tool}_{metric}"] = round(statistics.mean(vals), 4) if vals else ""
        rows.append(row)

    fieldnames = ["n_messages"] + [f"{tool}_{m}" for tool in TOOLS for m in cross_metrics]
    out_csv  = os.path.join(RESULTS_DIR, "comparison_all_runs.csv")
    out_json = os.path.join(RESULTS_DIR, "comparison_all_runs.json")

    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    with open(out_json, "w") as f:
        json.dump({"ns": ns, "tools": TOOLS, "metrics": cross_metrics, "data": rows}, f, indent=2)

    print(f"\n📊 Comparação cross-N ({len(ns)} valores: {ns}):\n")
    header = f"{'N':>6}  {'eBPF avg':>10} {'sys avg':>10} {'prom avg':>10}  {'eBPF std':>10} {'sys std':>10} {'prom std':>10}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['n_messages']:>6}  "
            f"{str(row.get('ebpf_observador_latency_avg_ms','')):>10} "
            f"{str(row.get('sysstat_observador_latency_avg_ms','')):>10} "
            f"{str(row.get('prometheus_observador_latency_avg_ms','')):>10}  "
            f"{str(row.get('ebpf_observador_latency_stddev_ms','')):>10} "
            f"{str(row.get('sysstat_observador_latency_stddev_ms','')):>10} "
            f"{str(row.get('prometheus_observador_latency_stddev_ms','')):>10}"
        )
    print(f"\n✅ Salvo em {out_csv} e {out_json}")

def compare_aggregate(n, num_runs):
    """Agrega múltiplos runs de N mensagens: média ± desvio entre runs."""
    num_runs = int(num_runs)
    agg_metrics = [
        "observador_latency_avg_ms",
        "observador_latency_stddev_ms",
        "observador_latency_max_ms",
        "observador_latency_min_ms",
        "cpu_avg_pct",
        "mem_avg_mb",
        "collector_cpu_avg_pct",
        "collector_mem_avg_mb",
    ]

    # Pré-carrega todos os arquivos (evita re-leitura e warnings repetidos)
    all_data = {}
    for tool in TOOLS:
        for run_id in range(1, num_runs + 1):
            path = os.path.join(RESULTS_DIR, f"{tool}_{n}_run{run_id}_results.json")
            all_data[(tool, run_id)] = load(path)

    rows = []
    for metric in agg_metrics:
        row = {"metrica": METRICS_LABEL.get(metric, metric)}
        for tool in TOOLS:
            tl = TOOL_LABELS[tool]
            values = []
            for run_id in range(1, num_runs + 1):
                data = all_data[(tool, run_id)]
                val = data.get(metric)
                if val != "" and val is not None:
                    values.append(float(val))
            if values:
                mean = round(statistics.mean(values), 4)
                std  = round(statistics.stdev(values), 4) if len(values) > 1 else 0
                ci   = round(t_critical(len(values) - 1) * std / math.sqrt(len(values)), 4) if len(values) > 1 else 0
                row[tl]             = mean
                row[f"{tl}_std"]    = std
                row[f"{tl}_ci95"]   = ci
            else:
                row[tl]             = ""
                row[f"{tl}_std"]    = ""
                row[f"{tl}_ci95"]   = ""
        rows.append(row)

    out_csv  = os.path.join(RESULTS_DIR, f"comparison_{n}_{num_runs}runs.csv")
    out_json = os.path.join(RESULTS_DIR, f"comparison_{n}_{num_runs}runs.json")

    fieldnames = ["metrica"] + [f"{TOOL_LABELS[t]}{s}" for t in TOOLS for s in ("", "_std", "_ci95")]
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    with open(out_json, "w") as f:
        json.dump({"n_messages": n, "num_runs": num_runs, "tools": TOOLS,
                   "metrics": agg_metrics, "data": rows}, f, indent=2)

    print(f"\n📊 Agregação — {n} msgs × {num_runs} runs:\n")
    header = f"{'métrica':<35} {'eBPF mean±CI95':>20} {'sysstat mean±CI95':>20} {'prom mean±CI95':>20}"
    print(header)
    print("-" * len(header))
    for row in rows:
        def fmt(t):
            tl = TOOL_LABELS[t]
            m, ci = row.get(tl, ""), row.get(f"{tl}_ci95", "")
            return f"{m}±{ci}" if m != "" else "-"
        print(f"{row['metrica']:<35} {fmt('ebpf'):>20} {fmt('sysstat'):>20} {fmt('prometheus'):>20}")
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
