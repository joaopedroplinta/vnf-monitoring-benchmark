#!/usr/bin/env python3
"""
WAF TCP — TCC Gerenciamento de Rede
Porta: 8080
Protocolo: framing com 4 bytes big-endian de comprimento por mensagem.
Inspeciona cada payload com regras de segurança (SQLi, XSS, Path Traversal, RCE)
antes de responder ao cliente. Usa asyncio + ThreadPoolExecutor para alta concorrência.
"""
import asyncio
import concurrent.futures
import struct
import re
import json
import os
import time
import threading

HOST             = '0.0.0.0'
PORT             = 8080
_METRICS_PATH    = os.environ.get("WAF_METRICS_PATH", "/app/results/waf_metrics.json")
_WRITE_EVERY     = 100
_INSPECT_WORKERS = int(os.environ.get("WAF_INSPECT_WORKERS", os.cpu_count() or 4))

_stats_lock = threading.Lock()
_stats = {"count": 0, "total_ms": 0.0, "min_ms": None, "max_ms": 0.0}

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=_INSPECT_WORKERS)


def _flush(s: dict) -> None:
    if s["count"] == 0:
        return
    data = {
        "inspect_count":  s["count"],
        "inspect_avg_ms": round(s["total_ms"] / s["count"], 6),
        "inspect_min_ms": round(s["min_ms"] or 0.0, 6),
        "inspect_max_ms": round(s["max_ms"], 6),
    }
    try:
        with open(_METRICS_PATH, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[WARN] waf_metrics: {e}")


def _record(elapsed_ms: float) -> None:
    snapshot = None
    with _stats_lock:
        _stats["count"]    += 1
        _stats["total_ms"] += elapsed_ms
        if _stats["min_ms"] is None or elapsed_ms < _stats["min_ms"]:
            _stats["min_ms"] = elapsed_ms
        if elapsed_ms > _stats["max_ms"]:
            _stats["max_ms"] = elapsed_ms
        if _stats["count"] % _WRITE_EVERY == 0:
            snapshot = _stats.copy()
    if snapshot is not None:
        _flush(snapshot)


# ── Regras WAF ────────────────────────────────────────────────────────────────
WAF_RULES = [
    (re.compile(r"(\b(union|select|insert|update|delete|drop|truncate|exec|execute)\b)", re.I), "SQLi"),
    (re.compile(r"(<script[\s\S]*?>[\s\S]*?</script>|javascript:|onerror=|onload=)", re.I), "XSS"),
    (re.compile(r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e/|\.\.%2f)", re.I), "PathTraversal"),
    (re.compile(r"(\b(cmd|bash|sh|powershell|wget|curl|chmod|nc|ncat|netcat)\b)", re.I), "RCE"),
    (re.compile(r"(\x00|\x1a|%00)", re.I), "NullByte"),
]

def inspect_and_record(payload: bytes) -> tuple[bool, str]:
    """Inspeção + contabilização (executada no thread pool)."""
    text = payload.decode("utf-8", errors="replace")
    t0 = time.perf_counter()
    for pattern, name in WAF_RULES:
        if pattern.search(text):
            _record((time.perf_counter() - t0) * 1000)
            return True, name
    _record((time.perf_counter() - t0) * 1000)
    return False, "OK"


async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Lida com uma conexão persistente: múltiplas mensagens com framing 4-byte."""
    loop = asyncio.get_event_loop()
    try:
        while True:
            header = await reader.readexactly(4)
            length = struct.unpack(">I", header)[0]
            payload = await reader.readexactly(length)

            blocked, reason = await loop.run_in_executor(
                _executor, inspect_and_record, payload
            )

            response = f"BLOCKED:{reason}\n".encode() if blocked else b"ALLOWED:OK\n"
            writer.write(response)
            await writer.drain()
    except asyncio.IncompleteReadError:
        pass  # cliente fechou a conexão normalmente
    except Exception as e:
        print(f"[ERRO] {writer.get_extra_info('peername')}: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def main_async() -> None:
    server = await asyncio.start_server(handle_connection, HOST, PORT, reuse_port=True)
    addrs = [s.getsockname() for s in server.sockets]
    print(f"✅ WAF asyncio escutando em {addrs} | inspect_workers={_INSPECT_WORKERS}", flush=True)
    async with server:
        await server.serve_forever()


def main():
    print("=" * 50)
    print(f"  WAF TCP — porta {PORT}")
    print(f"  Regras: SQLi, XSS, PathTraversal, RCE, NullByte")
    print(f"  Modo: asyncio + ThreadPoolExecutor({_INSPECT_WORKERS})")
    print("=" * 50)
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
