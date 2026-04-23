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
import json
import os
import time
from datetime import datetime

HOST = '0.0.0.0'
PORT = 8080
_METRICS_PATH = os.environ.get("WAF_METRICS_PATH", "/app/results/waf_metrics.json")
_WRITE_EVERY  = 100  # grava a cada N inspeções

_stats_lock = threading.Lock()
_stats = {"count": 0, "total_ms": 0.0, "min_ms": float("inf"), "max_ms": 0.0}


def _record(elapsed_ms: float) -> None:
    with _stats_lock:
        _stats["count"]    += 1
        _stats["total_ms"] += elapsed_ms
        if elapsed_ms < _stats["min_ms"]:
            _stats["min_ms"] = elapsed_ms
        if elapsed_ms > _stats["max_ms"]:
            _stats["max_ms"] = elapsed_ms
        if _stats["count"] % _WRITE_EVERY == 0:
            _flush(_stats.copy())


def _flush(s: dict) -> None:
    data = {
        "inspect_count":  s["count"],
        "inspect_avg_ms": round(s["total_ms"] / s["count"], 6),
        "inspect_min_ms": round(s["min_ms"], 6),
        "inspect_max_ms": round(s["max_ms"], 6),
    }
    try:
        with open(_METRICS_PATH, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[WARN] waf_metrics: {e}")

# ── Regras WAF ────────────────────────────────────────────────────────────────
WAF_RULES = [
    (re.compile(r"(\b(union|select|insert|update|delete|drop|truncate|exec|execute)\b)", re.I), "SQLi"),
    (re.compile(r"(<script[\s\S]*?>[\s\S]*?</script>|javascript:|onerror=|onload=)", re.I), "XSS"),
    (re.compile(r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e/|\.\.%2f)", re.I), "PathTraversal"),
    (re.compile(r"(\b(cmd|bash|sh|powershell|wget|curl|chmod|nc|ncat|netcat)\b)", re.I), "RCE"),
    (re.compile(r"(\x00|\x1a|%00)", re.I), "NullByte"),
]

def inspect(payload: bytes) -> tuple[bool, str]:
    """Retorna (bloqueado, motivo). False = permitido."""
    text = payload.decode("utf-8", errors="replace")
    for pattern, name in WAF_RULES:
        if pattern.search(text):
            return True, name
    return False, "OK"

def handle_client(conn, addr):
    with conn:
        try:
            conn.settimeout(5)
            chunks = []
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            data = b"".join(chunks)

            t0 = time.perf_counter()
            blocked, reason = inspect(data)
            _record((time.perf_counter() - t0) * 1000)

            if blocked:
                response = f"BLOCKED:{reason}\n".encode()
            else:
                response = b"ALLOWED:OK\n"

            conn.sendall(response)

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
