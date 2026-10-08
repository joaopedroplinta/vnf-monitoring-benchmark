"""Recalcula inspect_* do resumo a partir da última amostra com inspect_count > 0.

O WAF grava waf_metrics.json sem escrita atômica; o observador às vezes lê o arquivo
cortado e devolve zeros. Quando isso cai na última amostra, o resumo fica zerado.
As amostras brutas não são alteradas. Uso: python3 scripts/fix_inspect.py <pasta> [--dry]
"""
import glob, json, sys

KEYS = ("inspect_count", "inspect_avg_ms", "inspect_min_ms", "inspect_max_ms")


def main():
    folder, dry = sys.argv[1], "--dry" in sys.argv
    fixed = total = 0
    for path in sorted(glob.glob(f"{folder}/*_run*_results.json")):
        d = json.load(open(path))
        total += 1
        if d.get("inspect_count"):
            continue
        valid = [s for s in d.get("samples", []) if s.get("inspect_count")]
        if not valid:
            print(f"sem amostra válida: {path}")
            continue
        d.update({k: valid[-1][k] for k in KEYS})
        fixed += 1
        if not dry:
            json.dump(d, open(path, "w"), indent=2)
    print(f"{fixed}/{total} corrigidos" + (" (dry-run)" if dry else ""))


if __name__ == "__main__":
    main()
