"""Agregações do benchmark, compartilhadas pelas visualizações."""
import pandas as pd

LABEL = {"ebpf": "eBPF", "sysstat": "Sysstat", "prometheus": "Prometheus", "docker": "Docker"}
COLOR = {"eBPF": "#52d4df", "Sysstat": "#f2bd68", "Prometheus": "#a8b2ff", "Docker": "#f58c9b"}
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
       7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
       13: 2.16, 14: 2.145, 15: 2.131, 16: 2.12, 17: 2.11, 18: 2.101,
       19: 2.093, 20: 2.086, 21: 2.08, 22: 2.074, 23: 2.069, 24: 2.064,
       25: 2.06, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045}


def number(value, decimals=0):
    return f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def volume(value):
    if value >= 1_000_000:
        return f"{number(value / 1_000_000, 1).removesuffix(',0')} M"
    if value >= 1_000:
        return f"{number(value / 1_000, 1).removesuffix(',0')} mil"
    return number(value)


def summary(df, metric):
    groups = df.groupby(["Ferramenta", "n", "N"], observed=True)[metric].agg(
        ["mean", "std", "count"]
    ).reset_index()
    groups["ci"] = groups.apply(
        lambda r: T95.get(int(r["count"]) - 1, 1.96) * r["std"] / r["count"] ** 0.5
        if r["count"] > 1 else float("nan"), axis=1,
    )
    return groups.sort_values("n")


def confidence_separated(df, first, second):
    """Verifica a separação dos ICs por volume, sem misturar cargas distintas."""
    s = summary(df, "rtt_ms")
    for n in df["n"].unique():
        group = s[s["n"] == n].set_index("Ferramenta")
        if first not in group.index or second not in group.index:
            return False
        a, b = group.loc[first], group.loc[second]
        if pd.isna(a["ci"]) or pd.isna(b["ci"]) or a["mean"] + a["ci"] >= b["mean"] - b["ci"]:
            return False
    return not df.empty
