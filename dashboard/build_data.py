"""Gera dashboard/data.csv (uma linha por execução) a partir dos JSONs de results/.

Uso: python3 dashboard/build_data.py [pasta_de_resultados]   (padrão: results/)
"""
import csv, glob, json, os, re, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results")
OUT = os.path.join(os.path.dirname(__file__), "data.csv")
FIELDS = {
    "rtt_ms": "observador_latency_avg_ms", "rtt_std_ms": "observador_latency_stddev_ms",
    "cpu_waf": "cpu_avg_pct", "mem_waf_mb": "mem_avg_mb",
    "cpu_obs": "collector_cpu_avg_pct", "mem_obs_mb": "collector_mem_avg_mb",
    "inspect_count": "inspect_count", "inspect_avg_ms": "inspect_avg_ms",
    "bytes_rx": "bytes_rx", "bytes_tx": "bytes_tx",
}

rows = []
for f in sorted(glob.glob(os.path.join(SRC, "*_run*_results.json"))):
    m = re.match(r"(\w+?)_(\d+)_run(\d+)_results\.json", os.path.basename(f))
    d = json.load(open(f))
    rows.append({"tool": m[1], "n": int(m[2]), "run": int(m[3]), **{k: d.get(v) for k, v in FIELDS.items()}})

with open(OUT, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["tool", "n", "run", *FIELDS])
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} execuções -> {OUT}")
