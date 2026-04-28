#!/usr/bin/env python3
"""
Cliente TCP — TCC Gerenciamento de Rede
Bombardeia o WAF (porta 8080) com payloads pré-gerados.
Carrega os payloads de um arquivo binário gerado por scripts/gen_payloads.py.
"""
import socket
import struct
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

WAF_HOST      = 'localhost'
WAF_PORT      = 8080
WORKERS       = int(os.environ.get("WORKERS", 10))
PAYLOADS_FILE = os.environ.get("PAYLOADS_FILE", "")


def load_payloads(path: str) -> list[bytes]:
    """Lê arquivo binário gerado por gen_payloads.py."""
    with open(path, "rb") as f:
        (count,) = struct.unpack(">I", f.read(4))
        payloads = []
        for _ in range(count):
            (length,) = struct.unpack(">I", f.read(4))
            payloads.append(f.read(length))
    return payloads

def wait_for_server(host, port, max_attempts=30) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect((host, port))
            print(f"✅ WAF disponível após {attempt} tentativa(s).")
            return True
        except Exception:
            print(f"⏳ Aguardando WAF... tentativa {attempt}/{max_attempts}")
            time.sleep(1)
    return False

def send_payload(payload: bytes) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(10)
        s.connect((WAF_HOST, WAF_PORT))
        s.sendall(payload)
        s.shutdown(socket.SHUT_WR)
        response = s.recv(256).decode("utf-8", errors="replace").strip()
    return response

def main():
    if not PAYLOADS_FILE:
        print("❌ PAYLOADS_FILE não definido. Gere os payloads com:")
        print("   python3 scripts/gen_payloads.py <count>")
        print("   e exporte PAYLOADS_FILE=<caminho>")
        return

    print("=" * 50)
    print(f"  Cliente TCP — WAF {WAF_HOST}:{WAF_PORT}")
    print(f"  Arquivo: {PAYLOADS_FILE} | Workers: {WORKERS} | Sem delay")
    print("=" * 50)

    payloads = load_payloads(PAYLOADS_FILE)
    print(f"  {len(payloads):,} payloads carregados.")

    if not wait_for_server(WAF_HOST, WAF_PORT):
        print("❌ WAF não respondeu. Encerrando.")
        return

    print(f"\n🚀 Iniciando envio...")
    allowed = blocked = errors = 0
    t_start = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(send_payload, p): i for i, p in enumerate(payloads)}
        for future in as_completed(futures):
            i = futures[future]
            try:
                response = future.result()
                if response.startswith("BLOCKED"):
                    blocked += 1
                else:
                    allowed += 1
            except Exception as e:
                errors += 1
                print(f"[ERRO] payload {i}: {e}", flush=True)

    n = len(payloads)
    elapsed = round(time.time() - t_start, 2)
    rate    = round(n / elapsed, 1) if elapsed > 0 else 0
    print(f"\n✅ Concluído em {elapsed}s (~{rate} msg/s) — ALLOW:{allowed} BLOCK:{blocked} ERRO:{errors}")

if __name__ == "__main__":
    main()
