"""Gera dashboard/data.csv e dashboard/data_otimizada.csv (uma linha por execução) a partir dos JSONs de results/.

Uso:
  python3 dashboard/build_data.py                     # gera data.csv (oficial) e data_otimizada.csv (se results/otimizada existir)
  python3 dashboard/build_data.py <pasta> [saida.csv] # gera um CSV específico
"""
import csv, glob, json, os, re, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
FIELDS = {
    "rtt_ms": "observador_latency_avg_ms", "rtt_std_ms": "observador_latency_stddev_ms",
    "cpu_waf": "cpu_avg_pct", "mem_waf_mb": "mem_avg_mb",
    "cpu_obs": "collector_cpu_avg_pct", "mem_obs_mb": "collector_mem_avg_mb",
    "inspect_count": "inspect_count", "inspect_avg_ms": "inspect_avg_ms",
    "bytes_rx": "bytes_rx", "bytes_tx": "bytes_tx",
}


def build_csv(src_dir: str, out_path: str) -> None:
    rows = []
    for f in sorted(glob.glob(os.path.join(src_dir, "*_run*_results.json"))):
        m = re.match(r"(\w+?)_(\d+)_run(\d+)_results\.json", os.path.basename(f))
        if not m:
            continue
        with open(f) as fh:
            d = json.load(fh)
        rows.append({"tool": m[1], "n": int(m[2]), "run": int(m[3]), **{k: d.get(v) for k, v in FIELDS.items()}})

    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["tool", "n", "run", *FIELDS])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} execuções -> {out_path}")


if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    if len(sys.argv) > 1:
        src = sys.argv[1]
        out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(base_dir, "data.csv")
        build_csv(src, out)
    else:
        build_csv(os.path.join(ROOT, "results"), os.path.join(base_dir, "data.csv"))
        opt_dir = os.path.join(ROOT, "results", "otimizada")
        if os.path.isdir(opt_dir):
            build_csv(opt_dir, os.path.join(base_dir, "data_otimizada.csv"))
