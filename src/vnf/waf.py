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

def inspect(payload: bytes) -> tuple[bool, str]:
    """Retorna (bloqueado, motivo). False = permitido."""
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

            blocked, reason = inspect(data)

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
