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
from typing import Optional
import struct
import time
import os
import multiprocessing

WAF_HOST      = os.environ.get("WAF_HOST", 'localhost')
WAF_PORT      = int(os.environ.get("WAF_PORT", 8080))
WORKERS       = int(os.environ.get("WORKERS", 200))
# 1 = comportamento original (um processo). >1 = N processos, cada um com WORKERS/N conexões
# e uma fatia dos payloads (índice % N), para o cliente não limitar a vazão com o GIL.
PROCESSES     = int(os.environ.get("CLIENT_PROCESSES", 1))
PAYLOADS_FILE = os.environ.get("PAYLOADS_FILE", "")
QUEUE_SIZE    = int(os.environ.get("QUEUE_SIZE", 2000))


def _read_payload(f) -> Optional[bytes]:
    """Lê um payload do arquivo binário aberto. Retorna None no EOF."""
    header = f.read(4)
    if len(header) < 4:
        return None
    (length,) = struct.unpack(">I", header)
    return f.read(length)


async def payload_producer(path: str, queue: asyncio.Queue, num_workers: int, shard: int = 0, shards: int = 1) -> int:
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

        for i in range(count):
            if shards > 1 and i % shards != shard:
                # payload de outra fatia: pula sem ler o conteúdo
                header = await loop.run_in_executor(None, f.read, 4)
                if len(header) < 4:
                    break
                f.seek(struct.unpack(">I", header)[0], 1)
                continue
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

async def run_shard(shard: int = 0, shards: int = 1) -> tuple:
    """Envia a fatia `shard` de `shards` dos payloads. Retorna (count enviado, counters)."""
    workers = max(1, WORKERS // shards)
    payload_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
    counters = {"allowed": 0, "blocked": 0, "errors": 0}

    # Inicia produtor e workers concorrentemente
    producer_task = asyncio.create_task(
        payload_producer(PAYLOADS_FILE, payload_queue, workers, shard, shards)
    )
    worker_tasks = [
        asyncio.create_task(connection_worker(payload_queue, counters))
        for _ in range(workers)
    ]

    # Aguarda produtor terminar e depois todos os workers drenarem
    count = await producer_task
    await asyncio.gather(*worker_tasks)
    return count, counters


def _shard_main(shard: int, shards: int, out) -> None:
    out.put(asyncio.run(run_shard(shard, shards)))


def report(count: int, counters: dict, t_start: float) -> None:
    elapsed = round(time.time() - t_start, 2)
    rate = round(count / elapsed, 1) if elapsed > 0 else 0
    print(f"\n✅ Concluído em {elapsed}s (~{rate} msg/s) — "
          f"ALLOW:{counters['allowed']} BLOCK:{counters['blocked']} ERRO:{counters['errors']}")


async def main_async() -> None:
    if not await wait_for_server(WAF_HOST, WAF_PORT):
        print("❌ WAF não respondeu. Encerrando.")
        return

    print(f"\n🚀 Iniciando envio...")
    t_start = time.time()
    count, counters = await run_shard()
    report(count, counters, t_start)


def main_multiprocess() -> None:
    # o fork acontece fora do event loop, senão os filhos herdam o loop em execução
    if not asyncio.run(wait_for_server(WAF_HOST, WAF_PORT)):
        print("❌ WAF não respondeu. Encerrando.")
        return

    print(f"\n🚀 Iniciando envio ({PROCESSES} processos)...")
    t_start = time.time()
    ctx = multiprocessing.get_context("fork")
    out = ctx.Queue()
    procs = [ctx.Process(target=_shard_main, args=(k, PROCESSES, out)) for k in range(PROCESSES)]
    for p in procs:
        p.start()
    results = [out.get() for _ in procs]
    for p in procs:
        p.join()
    total = {k: sum(r[1][k] for r in results) for k in ("allowed", "blocked", "errors")}
    report(sum(r[0] for r in results), total, t_start)

def main():
    if not PAYLOADS_FILE:
        print("❌ PAYLOADS_FILE não definido. Gere os payloads com:")
        print("   python3 scripts/gen_payloads.py <count>")
        print("   e exporte PAYLOADS_FILE=<caminho>")
        return

    print("=" * 50)
    print(f"  Cliente TCP — WAF {WAF_HOST}:{WAF_PORT}")
    print(f"  Arquivo: {PAYLOADS_FILE} | Workers: {WORKERS} | Processos: {PROCESSES} | Queue: {QUEUE_SIZE} | asyncio + conexões persistentes")
    print("=" * 50)

    # Lê apenas o header para exibir o count sem carregar tudo na memória
    with open(PAYLOADS_FILE, "rb") as f:
        (count,) = struct.unpack(">I", f.read(4))
    print(f"  {count:,} payloads no arquivo (streaming, RAM ~ QUEUE_SIZE={QUEUE_SIZE}).")

    if PROCESSES > 1:
        main_multiprocess()
    else:
        asyncio.run(main_async())

if __name__ == "__main__":
    main()
