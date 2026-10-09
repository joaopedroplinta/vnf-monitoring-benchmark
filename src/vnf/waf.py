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
import multiprocessing
import signal

HOST             = '0.0.0.0'
PORT             = int(os.environ.get("WAF_PORT", 8080))
# 1 = comportamento original (um processo, GIL). >1 = N processos na mesma porta (SO_REUSEPORT),
# estatísticas agregadas em memória compartilhada. O observador soma CPU/RSS de todos os "waf.py".
_PROCESSES       = int(os.environ.get("WAF_PROCESSES", 1))
_METRICS_PATH    = os.environ.get("WAF_METRICS_PATH", "/app/results/waf_metrics.json")
_WRITE_EVERY     = 100
_INSPECT_WORKERS = int(os.environ.get("WAF_INSPECT_WORKERS", os.cpu_count() or 4))

_stats_lock = threading.Lock()
_stats = {"count": 0, "total_ms": 0.0, "min_ms": None, "max_ms": 0.0}

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=_INSPECT_WORKERS)
_shared = None  # multiprocessing.Array [count, total_ms, min_ms (-1 = nenhum), max_ms]; só com WAF_PROCESSES > 1


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
        tmp = _METRICS_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, _METRICS_PATH)  # atômico: o observador nunca lê o JSON cortado
    except Exception as e:
        print(f"[WARN] waf_metrics: {e}")


def _record_shared(elapsed_ms: float) -> None:
    snapshot = None
    with _shared.get_lock():
        _shared[0] += 1
        _shared[1] += elapsed_ms
        if _shared[2] < 0 or elapsed_ms < _shared[2]:
            _shared[2] = elapsed_ms
        if elapsed_ms > _shared[3]:
            _shared[3] = elapsed_ms
        if int(_shared[0]) % _WRITE_EVERY == 0:
            snapshot = {"count": int(_shared[0]), "total_ms": _shared[1],
                        "min_ms": None if _shared[2] < 0 else _shared[2], "max_ms": _shared[3]}
    if snapshot is not None:
        _flush(snapshot)


def _record(elapsed_ms: float) -> None:
    if _shared is not None:
        return _record_shared(elapsed_ms)
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


def _worker() -> None:
    asyncio.run(main_async())


def main():
    global _shared
    print("=" * 50)
    print(f"  WAF TCP — porta {PORT}")
    print(f"  Regras: SQLi, XSS, PathTraversal, RCE, NullByte")
    print(f"  Modo: asyncio + ThreadPoolExecutor({_INSPECT_WORKERS}) x {_PROCESSES} processo(s)")
    print("=" * 50)
    if _PROCESSES <= 1:
        return _worker()
    ctx = multiprocessing.get_context("fork")  # fork: o Array compartilhado é herdado pelos filhos
    _shared = ctx.Array("d", [0.0, 0.0, -1.0, 0.0])
    procs = [ctx.Process(target=_worker, daemon=True) for _ in range(_PROCESSES)]
    for p in procs:
        p.start()

    def stop(*_):
        for p in procs:
            p.terminate()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    for p in procs:
        p.join()


if __name__ == "__main__":
    main()
