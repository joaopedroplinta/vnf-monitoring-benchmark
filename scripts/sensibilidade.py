#!/usr/bin/env python3
"""Compara a coleta oficial (N=1M) com as configurações multiprocesso.

Uso: python3 scripts/sensibilidade.py [pasta_com_sens_cli4_e_sens_waf4cli4]   (padrão: results/)
Só considera runs completos (duration_s >= 80): o coletor grava o resultado aos poucos.
"""
import glob, json, math, os, statistics as st, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "results")
CFGS = [("base", "."), ("cliente x4", "sens_cli4"), ("WAF x4 + cliente x4", "sens_waf4cli4")]
TOOLS = ["ebpf", "sysstat", "prometheus", "docker"]
N = 1_000_000
FIELDS = [("RTT (ms)", "observador_latency_avg_ms", 4), ("inspeções", "inspect_count", 0),
          ("CPU WAF (%)", "cpu_avg_pct", 1), ("mem WAF (MB)", "mem_avg_mb", 1)]


def runs(cfg_dir, tool):
    base = os.path.join(ROOT, cfg_dir if cfg_dir != "." else "")
    # base: o oficial fica direto em results/ (recoleta)
    out = []
    for f in glob.glob(os.path.join(base, f"{tool}_{N}_run*_results.json")):
        d = json.load(open(f))
        if d["duration_s"] >= 80:
            out.append(d)
    return out


def ci(v):  # t de Student 95% (tabela só nos n usados aqui; 1,96 como aproximação acima de 30)
    t = {29: 2.045}.get(len(v) - 1, 1.96)
    return t * st.stdev(v) / math.sqrt(len(v)) if len(v) > 1 else 0.0


for tool in TOOLS:
    print(f"\n## {tool} (N = {N:,})")
    for label, cfg in CFGS:
        rs = runs(cfg, tool)
        if not rs:
            print(f"  {label:22} sem runs completos")
            continue
        cells = []
        for name, k, dec in FIELDS:
            v = [r[k] for r in rs]
            cells.append(f"{name} {st.mean(v):.{dec}f} ± {ci(v):.{dec}f}")
        pct = st.mean(r["inspect_count"] for r in rs) / N * 100
        print(f"  {label:22} n={len(rs):2} | " + " | ".join(cells) + f" | {pct:.0f}% de N")
