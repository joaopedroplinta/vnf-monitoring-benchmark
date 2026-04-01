#!/usr/bin/env python3
"""
WAF TCP — TCC Gerenciamento de Rede
Porta: 8080
Inspeciona cada payload com regras de segurança (SQLi, XSS, Path Traversal, RCE)
antes de responder ao cliente.
"""
import socket
import threading
import re
import time
import json
import os
from datetime import datetime

HOST = '0.0.0.0'
PORT = 8080

# ── Regras WAF ────────────────────────────────────────────────────────────────
WAF_RULES = [
    (re.compile(r"(\b(union|select|insert|update|delete|drop|truncate|exec|execute)\b)", re.I), "SQLi"),
    (re.compile(r"(<script[\s\S]*?>[\s\S]*?</script>|javascript:|onerror=|onload=)", re.I), "XSS"),
    (re.compile(r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e/|\.\.%2f)", re.I), "PathTraversal"),
    (re.compile(r"(\b(cmd|bash|sh|powershell|wget|curl|chmod|nc|ncat|netcat)\b)", re.I), "RCE"),
    (re.compile(r"(\x00|\x1a|%00)", re.I), "NullByte"),
]

# ── Métricas globais (compartilhadas com monitor_server.py via arquivo) ───────
METRICS_PATH = "/app/results/vnf_metrics.json"
os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)

metrics = {
    "connections":  0,
    "bytes_rx":     0,
    "bytes_tx":     0,
    "blocked":      0,
    "allowed":      0,
    "lock":         threading.Lock(),
}

start_time = time.time()

def inspect(payload: bytes) -> tuple[bool, str]:
    """Retorna (bloqueado, motivo). False = permitido."""
    # Simula carga de CPU para o monitoramento detectar
    # Um pequeno loop de cálculo matemático
    x = 0
    for i in range(1000):
        x += i * i
        
    try:
        text = payload.decode("utf-8", errors="replace")
    except Exception:
        return True, "DecodeError"
    for pattern, name in WAF_RULES:
        if pattern.search(text):
            return True, name
    return False, "OK"

def save_metrics():
    import psutil
    try:
        proc = psutil.Process(os.getpid())
        # Chamamos uma vez para inicializar se necessário
        cpu = proc.cpu_percent(interval=0.1)
        mem = proc.memory_info().rss / (1024 * 1024)
    except Exception:
        cpu, mem = 0.0, 0.0

    with metrics["lock"]:
        snapshot = {
            "timestamp":   datetime.utcnow().isoformat(),
            "uptime_s":    round(time.time() - start_time, 2),
            "connections": metrics["connections"],
            "bytes_rx":    metrics["bytes_rx"],
            "bytes_tx":    metrics["bytes_tx"],
            "blocked":     metrics["blocked"],
            "allowed":     metrics["allowed"],
            "cpu_pct":     cpu,
            "mem_mb":      round(mem, 2),
        }
    with open(METRICS_PATH, "w") as f:
        json.dump(snapshot, f)

def metrics_writer():
    """Salva métricas em disco a cada 2s para o monitor_server.py ler."""
    while True:
        time.sleep(2)
        try:
            save_metrics()
        except Exception:
            pass

def handle_client(conn, addr):
    with metrics["lock"]:
        metrics["connections"] += 1

    with conn:
        try:
            # Recebe payload (pode ser grande — lê até EOF ou timeout)
            conn.settimeout(5)
            chunks = []
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            data = b"".join(chunks)

            with metrics["lock"]:
                metrics["bytes_rx"] += len(data)

            blocked, reason = inspect(data)

            if blocked:
                response = f"BLOCKED:{reason}\n".encode()
                with metrics["lock"]:
                    metrics["blocked"] += 1
            else:
                response = b"ALLOWED:OK\n"
                with metrics["lock"]:
                    metrics["allowed"] += 1

            conn.sendall(response)
            with metrics["lock"]:
                metrics["bytes_tx"] += len(response)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] {addr} | "
                  f"{len(data)}B | {'BLOCK:'+reason if blocked else 'ALLOW'}")
        except socket.timeout:
            pass
        except Exception as e:
            print(f"[ERRO] {addr}: {e}")

def main():
    print("=" * 50)
    print(f"  WAF TCP — porta {PORT}")
    print(f"  Regras: SQLi, XSS, PathTraversal, RCE, NullByte")
    print("=" * 50)

    threading.Thread(target=metrics_writer, daemon=True).start()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(100)
    print(f"✅ WAF escutando em {HOST}:{PORT}", flush=True)

    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()