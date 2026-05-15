#!/usr/bin/env python3
"""
Cliente TCP — TCC Gerenciamento de Rede
Bombardeia o WAF (porta 8080) com payloads pré-gerados.
Protocolo: framing com 4 bytes big-endian de comprimento por mensagem.
Cada worker é uma coroutine asyncio com conexão persistente — sem limite de concorrência.
Payloads são lidos em streaming (lazy) via asyncio.Queue para manter RAM constante
independente do número total de mensagens (N=5M, 10M, etc.).
"""
import asyncio
import struct
import time
import os

WAF_HOST      = 'localhost'
WAF_PORT      = 8080
WORKERS       = int(os.environ.get("WORKERS", 200))
PAYLOADS_FILE = os.environ.get("PAYLOADS_FILE", "")
QUEUE_SIZE    = int(os.environ.get("QUEUE_SIZE", 2000))


def _read_payload(f) -> bytes | None:
    """Lê um payload do arquivo binário aberto. Retorna None no EOF."""
    header = f.read(4)
    if len(header) < 4:
        return None
    (length,) = struct.unpack(">I", header)
    return f.read(length)


async def payload_producer(path: str, queue: asyncio.Queue, num_workers: int) -> int:
    """
    Coroutine produtora: lê payloads do arquivo binário de forma lazy e os coloca
    na queue. Ao terminar, enfileira `num_workers` sentinelas None para sinalizar
    fim a cada worker. Retorna o count lido do header do arquivo.
    """
    loop = asyncio.get_event_loop()

    with open(path, "rb") as f:
        # Lê o header (count total) no executor para não bloquear o event loop
        header_bytes = await loop.run_in_executor(None, f.read, 4)
        (count,) = struct.unpack(">I", header_bytes)

        for _ in range(count):
            payload = await loop.run_in_executor(None, _read_payload, f)
            if payload is None:
                break
            await queue.put(payload)

    # Enfileira sentinelas para encerrar cada worker
    for _ in range(num_workers):
        await queue.put(None)

    return count


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
    """Coroutine: conexão persistente, consome a fila até receber sentinela None."""
    reader, writer = None, None
    while True:
        payload = await payload_queue.get()
        if payload is None:
            # Sentinela: encerra este worker
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

async def main_async() -> None:
    if not await wait_for_server(WAF_HOST, WAF_PORT):
        print("❌ WAF não respondeu. Encerrando.")
        return

    payload_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
    counters = {"allowed": 0, "blocked": 0, "errors": 0}

    print(f"\n🚀 Iniciando envio...")
    t_start = time.time()

    # Inicia produtor e workers concorrentemente
    producer_task = asyncio.create_task(
        payload_producer(PAYLOADS_FILE, payload_queue, WORKERS)
    )
    worker_tasks = [
        asyncio.create_task(connection_worker(payload_queue, counters))
        for _ in range(WORKERS)
    ]

    # Aguarda produtor terminar e depois todos os workers drenarem
    count = await producer_task
    await asyncio.gather(*worker_tasks)

    elapsed = round(time.time() - t_start, 2)
    rate = round(count / elapsed, 1) if elapsed > 0 else 0
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
    print(f"  Arquivo: {PAYLOADS_FILE} | Workers: {WORKERS} | Queue: {QUEUE_SIZE} | asyncio + conexões persistentes")
    print("=" * 50)

    # Lê apenas o header para exibir o count sem carregar tudo na memória
    with open(PAYLOADS_FILE, "rb") as f:
        (count,) = struct.unpack(">I", f.read(4))
    print(f"  {count:,} payloads no arquivo (streaming, RAM ~ QUEUE_SIZE={QUEUE_SIZE}).")

    asyncio.run(main_async())

if __name__ == "__main__":
    main()
