#!/usr/bin/env python3
"""
Cliente TCP — TCC Gerenciamento de Rede
Bombardeia o WAF (porta 8080) com payloads pré-gerados.
Protocolo: framing com 4 bytes big-endian de comprimento por mensagem.
Cada worker é uma coroutine asyncio com conexão persistente — sem limite de concorrência.
"""
import asyncio
import struct
import time
import os

WAF_HOST      = 'localhost'
WAF_PORT      = 8080
WORKERS       = int(os.environ.get("WORKERS", 200))
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

async def wait_for_server(host, port, max_attempts=30) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            print(f"✅ WAF disponível após {attempt} tentativa(s).")
            return True
        except Exception:
            print(f"⏳ Aguardando WAF... tentativa {attempt}/{max_attempts}")
            await asyncio.sleep(1)
    return False

async def connection_worker(payload_queue: asyncio.Queue, counters: dict) -> None:
    """Coroutine: conexão persistente, drena a fila até esvaziar."""
    reader, writer = None, None
    while True:
        try:
            payload = payload_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        # Conecta (ou reconecta após erro)
        if writer is None:
            try:
                reader, writer = await asyncio.open_connection(WAF_HOST, WAF_PORT)
            except Exception as e:
                counters["errors"] += 1
                print(f"[ERRO] conexão: {e}", flush=True)
                continue

        try:
            writer.write(struct.pack(">I", len(payload)) + payload)
            await writer.drain()
            response = await reader.readuntil(b"\n")
            if response.startswith(b"BLOCKED"):
                counters["blocked"] += 1
            else:
                counters["allowed"] += 1
        except Exception as e:
            counters["errors"] += 1
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            reader, writer = None, None

    if writer:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

async def main_async(payloads: list[bytes]) -> None:
    if not await wait_for_server(WAF_HOST, WAF_PORT):
        print("❌ WAF não respondeu. Encerrando.")
        return

    payload_queue: asyncio.Queue = asyncio.Queue()
    for p in payloads:
        payload_queue.put_nowait(p)

    counters = {"allowed": 0, "blocked": 0, "errors": 0}

    print(f"\n🚀 Iniciando envio...")
    t_start = time.time()

    await asyncio.gather(*[
        connection_worker(payload_queue, counters)
        for _ in range(WORKERS)
    ])

    elapsed = round(time.time() - t_start, 2)
    n = len(payloads)
    rate = round(n / elapsed, 1) if elapsed > 0 else 0
    print(f"\n✅ Concluído em {elapsed}s (~{rate} msg/s) — "
          f"ALLOW:{counters['allowed']} BLOCK:{counters['blocked']} ERRO:{counters['errors']}")

def main():
    if not PAYLOADS_FILE:
        print("❌ PAYLOADS_FILE não definido. Gere os payloads com:")
        print("   python3 scripts/gen_payloads.py <count>")
        print("   e exporte PAYLOADS_FILE=<caminho>")
        return

    print("=" * 50)
    print(f"  Cliente TCP — WAF {WAF_HOST}:{WAF_PORT}")
    print(f"  Arquivo: {PAYLOADS_FILE} | Workers: {WORKERS} | asyncio + conexões persistentes")
    print("=" * 50)

    payloads = load_payloads(PAYLOADS_FILE)
    print(f"  {len(payloads):,} payloads carregados.")

    asyncio.run(main_async(payloads))

if __name__ == "__main__":
    main()
