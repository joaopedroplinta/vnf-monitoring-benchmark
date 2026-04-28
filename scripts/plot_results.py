#!/usr/bin/env python3
"""
Gera gráficos dos resultados do benchmark TCC.

Gráficos gerados em results/plots/:
  1. latencia_por_n.png       — Latência média por N com IC95% (linha)
  2. boxplot_latencia.png     — Distribuição de latência por ferramenta × N (boxplot)
  3. memoria_observador.png   — Memória do observador por ferramenta × N (barras)
  4. cpu_waf.png              — CPU média do WAF por ferramenta × N (barras)

Uso:
  python3 scripts/plot_results.py
"""

import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# ── Configuração ──────────────────────────────────────────────────────────────

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
PLOTS_DIR   = os.path.join(RESULTS_DIR, "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)

TOOLS       = ["ebpf", "sysstat", "prometheus"]
TOOL_LABELS = {"ebpf": "eBPF", "sysstat": "sysstat", "prometheus": "Prometheus"}
COLORS      = {"ebpf": "#2196F3", "sysstat": "#FF9800", "prometheus": "#4CAF50"}
NS          = [100_000, 500_000, 1_000_000]
NS_LABELS   = {100_000: "100k", 500_000: "500k", 1_000_000: "1M"}

plt.rcParams.update({
    "font.family":  "DejaVu Sans",
    "font.size":    11,
    "axes.grid":    True,
    "grid.alpha":   0.4,
    "figure.dpi":   150,
})

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path):
    with open(path) as f:
        return json.load(f)

def find_row(data_list, keyword):
    """Retorna a primeira linha cujo campo 'metrica' contenha keyword (case-insensitive)."""
    kw = keyword.lower()
    for row in data_list:
        if kw in row.get("metrica", "").lower():
            return row
    return {}

def load_30runs(n):
    path = os.path.join(RESULTS_DIR, f"comparison_{n}_30runs.json")
    return load_json(path)

def load_individual_runs(tool, n):
    """Carrega todos os run files disponíveis para ferramenta+N e retorna lista de dicts."""
    records = []
    for fname in sorted(os.listdir(RESULTS_DIR)):
        if re.match(rf"{tool}_{n}_run\d+_results\.json", fname):
            records.append(load_json(os.path.join(RESULTS_DIR, fname)))
    return records

# ── Gráfico 1: Latência média por N (linhas + IC95%) ─────────────────────────

def plot_latencia_por_n():
    fig, ax = plt.subplots(figsize=(7, 4.5))

    x = np.array([1, 2, 3])
    x_labels = [NS_LABELS[n] for n in NS]
    width = 0.22
    offsets = {"ebpf": -width, "sysstat": 0, "prometheus": width}

    for tool in TOOLS:
        means, cis = [], []
        for n in NS:
            d = load_30runs(n)
            row = find_row(d["data"], "latência média")
            tl = TOOL_LABELS[tool]
            means.append(row.get(tl, 0))
            cis.append(row.get(f"{tl}_ci95", 0))

        ax.bar(
            x + offsets[tool],
            means,
            width=width * 0.9,
            yerr=cis,
            label=TOOL_LABELS[tool],
            color=COLORS[tool],
            capsize=4,
            error_kw={"elinewidth": 1.2},
        )

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    ax.set_xlabel("Número de mensagens (N)")
    ax.set_ylabel("Latência média (ms)")
    ax.set_title("Latência média do observador por N\n(média ± IC95%, 30 runs)")
    ax.legend()
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "latencia_por_n.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"✅ {out}")

# ── Gráfico 2: Boxplot de latência por ferramenta × N ────────────────────────

def plot_boxplot_latencia():
    fig, axes = plt.subplots(1, 3, figsize=(12, 5), sharey=True)

    for ax, n in zip(axes, NS):
        data_per_tool = []
        for tool in TOOLS:
            runs = load_individual_runs(tool, n)
            values = [r.get("observador_latency_avg_ms", 0) for r in runs if r]
            data_per_tool.append(values)

        bp = ax.boxplot(
            data_per_tool,
            patch_artist=True,
            medianprops={"color": "black", "linewidth": 1.5},
            whiskerprops={"linewidth": 1.2},
            capprops={"linewidth": 1.2},
            flierprops={"marker": "o", "markersize": 4, "alpha": 0.5},
        )
        for patch, tool in zip(bp["boxes"], TOOLS):
            patch.set_facecolor(COLORS[tool])
            patch.set_alpha(0.75)

        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels([TOOL_LABELS[t] for t in TOOLS])
        ax.set_title(f"N = {NS_LABELS[n]}")
        ax.set_xlabel("Ferramenta")

    axes[0].set_ylabel("Latência média por run (ms)")
    fig.suptitle("Distribuição da latência do observador (30 runs)", y=1.01)
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "boxplot_latencia.png")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"✅ {out}")

# ── Gráfico 3: Memória do observador por ferramenta × N ──────────────────────

def plot_memoria_observador():
    fig, ax = plt.subplots(figsize=(7, 4.5))

    x = np.array([1, 2, 3])
    x_labels = [NS_LABELS[n] for n in NS]
    width = 0.22
    offsets = {"ebpf": -width, "sysstat": 0, "prometheus": width}

    for tool in TOOLS:
        means, cis = [], []
        for n in NS:
            d = load_30runs(n)
            row = find_row(d["data"], "memória média")
            # busca linha do observador/coletor (não do WAF)
            row = find_row(d["data"], "observador") or find_row(d["data"], "coletor")
            # filtra para pegar a linha de memória do observador especificamente
            for r in d["data"]:
                label = r.get("metrica", "").lower()
                if "memória" in label and ("observador" in label or "coletor" in label):
                    row = r
                    break
            tl = TOOL_LABELS[tool]
            means.append(row.get(tl, 0))
            cis.append(row.get(f"{tl}_ci95", 0))

        ax.bar(
            x + offsets[tool],
            means,
            width=width * 0.9,
            yerr=cis,
            label=TOOL_LABELS[tool],
            color=COLORS[tool],
            capsize=4,
            error_kw={"elinewidth": 1.2},
        )

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    ax.set_xlabel("Número de mensagens (N)")
    ax.set_ylabel("Memória média (MB)")
    ax.set_title("Memória do observador por N\n(média ± IC95%, 30 runs)")
    ax.legend()
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "memoria_observador.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"✅ {out}")

# ── Gráfico 4: CPU média do WAF por ferramenta × N ───────────────────────────

def plot_cpu_waf():
    fig, ax = plt.subplots(figsize=(7, 4.5))

    x = np.array([1, 2, 3])
    x_labels = [NS_LABELS[n] for n in NS]
    width = 0.22
    offsets = {"ebpf": -width, "sysstat": 0, "prometheus": width}

    for tool in TOOLS:
        means, cis = [], []
        for n in NS:
            d = load_30runs(n)
            row = {}
            for r in d["data"]:
                label = r.get("metrica", "").lower()
                if "cpu" in label and "waf" in label:
                    row = r
                    break
            tl = TOOL_LABELS[tool]
            means.append(row.get(tl, 0))
            cis.append(row.get(f"{tl}_ci95", 0))

        ax.bar(
            x + offsets[tool],
            means,
            width=width * 0.9,
            yerr=cis,
            label=TOOL_LABELS[tool],
            color=COLORS[tool],
            capsize=4,
            error_kw={"elinewidth": 1.2},
        )

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    ax.set_xlabel("Número de mensagens (N)")
    ax.set_ylabel("CPU média (%)")
    ax.set_title("CPU média do WAF por N\n(média ± IC95%, 30 runs)")
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.legend()
    fig.tight_layout()
    out = os.path.join(PLOTS_DIR, "cpu_waf.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"✅ {out}")

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Salvando gráficos em {PLOTS_DIR}/\n")
    plot_latencia_por_n()
    plot_boxplot_latencia()
    plot_memoria_observador()
    plot_cpu_waf()
    print("\nPronto.")
