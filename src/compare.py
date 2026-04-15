#!/usr/bin/env python3
"""
Comparador v2 — TCC Gerenciamento de Rede
Gera comparison.csv e comparison.json comparando as 3 ferramentas
com foco na métrica principal: tempo de monitoramento (média + desvio padrão).
"""
import json, csv, os

# Detectar se estamos rodando dentro do container ou no host
RESULTS_DIR = "/app/results" if os.path.exists("/app/results") else os.path.join(os.getcwd(), "results")
OUTPUT_CSV   = os.path.join(RESULTS_DIR, "comparison.csv")
OUTPUT_JSON  = os.path.join(RESULTS_DIR, "comparison.json")

FILES = {
    "ebpf":       os.path.join(RESULTS_DIR, "ebpf_results.json"),
    "sysstat":    os.path.join(RESULTS_DIR, "sysstat_results.json"),
    "prometheus": os.path.join(RESULTS_DIR, "prometheus_results.json"),
}

METRICS = [
    ("monitor_latency_avg_ms",    "Latência média monitoramento (ms)"),
    ("monitor_latency_stddev_ms", "Desvio padrão monitoramento (ms)"),
    ("monitor_latency_max_ms",    "Latência máx monitoramento (ms)"),
    ("monitor_latency_min_ms",    "Latência mín monitoramento (ms)"),
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

def main():
    data = {k: load(v) for k, v in FILES.items()}

    rows = []
    for key, label in METRICS:
        row = {"metrica": key, "descricao": label}
        for tool in ["ebpf", "sysstat", "prometheus"]:
            row[tool] = data[tool].get(key, "")
        rows.append(row)

    # CSV
    with open(OUTPUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["metrica", "ebpf", "sysstat", "prometheus"])
        w.writeheader()
        for row in rows:
            w.writerow({k: row[k] for k in ["metrica", "ebpf", "sysstat", "prometheus"]})

    # JSON
    comparison = {
        "tools": ["ebpf", "sysstat", "prometheus"],
        "metrics": rows,
        "raw": data,
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(comparison, f, indent=2)

    print("\n📊 Comparação gerada:\n")
    header = f"{'métrica':<35} {'eBPF':>12} {'sysstat':>12} {'prometheus':>12}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(f"{row['metrica']:<35} {str(row.get('ebpf','')):>12} "
              f"{str(row.get('sysstat','')):>12} {str(row.get('prometheus','')):>12}")
    print(f"\n✅ Salvo em {OUTPUT_CSV} e {OUTPUT_JSON}")

if __name__ == "__main__":
    main()