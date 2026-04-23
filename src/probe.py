#!/usr/bin/env python3
"""
Probe UDP — TCC Gerenciamento de Rede
Mede a latência de monitoramento (round-trip UDP) de qualquer observador.
Configurado via variáveis de ambiente:
  COLLECTOR    — nome da ferramenta (ebpf | sysstat | prometheus)
  RESULTS_PATH — caminho do JSON de saída
  DURATION     — duração da coleta em segundos (padrão: 60)
  OBSERVADOR_HOST — host do observador (padrão: 127.0.0.1)
  OBSERVADOR_PORT — porta UDP do observador (padrão: 9999)
"""
import signal, sys
import socket, time, json, os, statistics
from datetime import datetime

# Garante que SIGTERM (docker compose down) salva resultados antes de sair
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

COLLECTOR    = os.environ.get("COLLECTOR",    "unknown")
RESULTS_PATH = os.environ.get("RESULTS_PATH", f"/app/results/{COLLECTOR}_results.json")
DURATION     = int(os.environ.get("DURATION",     60))
OBSERVADOR_HOST = os.environ.get("OBSERVADOR_HOST", "127.0.0.1")
OBSERVADOR_PORT = int(os.environ.get("OBSERVADOR_PORT", 9999))
INTERVAL     = 1
SAVE_INTERVAL = 10

os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

def query() -> tuple[float, dict]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    try:
        t0 = time.time_ns()
        sock.sendto(b"GET", (OBSERVADOR_HOST, OBSERVADOR_PORT))
        data, _ = sock.recvfrom(65536)
        lat_ms = round((time.time_ns() - t0) / 1e6, 4)
        return lat_ms, json.loads(data.decode("utf-8"))
    finally:
        sock.close()

def save(start_time, latencies, samples):
    if not samples:
        print(f"⚠️  [{COLLECTOR}] nenhuma amostra coletada — arquivo não será salvo", flush=True)
        return
    last = samples[-1]
    result = {
        "collector":                 COLLECTOR,
        "timestamp":                 datetime.utcnow().isoformat(),
        "duration_s":                round(time.time() - start_time, 2),
        "observador_latency_avg_ms":    round(statistics.mean(latencies), 4)   if latencies else 0,
        "observador_latency_stddev_ms": round(statistics.stdev(latencies), 4)  if len(latencies) > 1 else 0,
        "observador_latency_max_ms":    round(max(latencies), 4)               if latencies else 0,
        "observador_latency_min_ms":    round(min(latencies), 4)               if latencies else 0,
        "observador_samples":           len(latencies),
        "latencies_raw":             latencies,
        "bytes_rx":                  last.get("bytes_rx", 0),
        "bytes_tx":                  last.get("bytes_tx", 0),
        "cpu_avg_pct":               round(statistics.mean([s["cpu_pct"]           for s in samples]), 2),
        "mem_avg_mb":                round(statistics.mean([s["mem_mb"]            for s in samples]), 2),
        "collector_cpu_avg_pct":     round(statistics.mean([s["collector_cpu_pct"] for s in samples]), 2),
        "collector_mem_avg_mb":      round(statistics.mean([s["collector_mem_mb"]  for s in samples]), 2),
        "inspect_count":             last.get("inspect_count", 0),
        "inspect_avg_ms":            last.get("inspect_avg_ms", 0.0),
        "inspect_min_ms":            last.get("inspect_min_ms", 0.0),
        "inspect_max_ms":            last.get("inspect_max_ms", 0.0),
        "samples":                   samples,
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n💾 [{COLLECTOR}] salvo | lat_avg={result['observador_latency_avg_ms']}ms | n={result['observador_samples']}\n")

def wait_ready(max_wait: int = 60) -> None:
    """Aguarda o observador responder antes de iniciar a medição."""
    print(f"  Aguardando observador em {OBSERVADOR_HOST}:{OBSERVADOR_PORT}...", flush=True)
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            query()
            print("  Observador pronto. Iniciando coleta.", flush=True)
            return
        except Exception:
            time.sleep(0.5)
    print(f"  AVISO: observador não respondeu em {max_wait}s. Iniciando mesmo assim.", flush=True)


def main():
    print("=" * 55)
    print(f"  Probe [{COLLECTOR}] — {OBSERVADOR_HOST}:{OBSERVADOR_PORT}")
    print("=" * 55)

    wait_ready()
    start_time = time.time()
    last_save  = time.time()
    latencies  = []
    samples    = []

    try:
        while time.time() - start_time < DURATION:
            now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            try:
                lat_ms, m = query()
                latencies.append(lat_ms)
                sample = {
                    "time":              now,
                    "latency_ms":        lat_ms,
                    "bytes_rx":          m.get("bytes_rx", 0),
                    "bytes_tx":          m.get("bytes_tx", 0),
                    "cpu_pct":           m.get("cpu_pct", 0),
                    "mem_mb":            m.get("mem_mb", 0),
                    "collector_cpu_pct": m.get("collector_cpu_pct", 0),
                    "collector_mem_mb":  m.get("collector_mem_mb", 0),
                    "inspect_count":     m.get("inspect_count", 0),
                    "inspect_avg_ms":    m.get("inspect_avg_ms", 0.0),
                    "inspect_min_ms":    m.get("inspect_min_ms", 0.0),
                    "inspect_max_ms":    m.get("inspect_max_ms", 0.0),
                }
                samples.append(sample)
                print(f"[{now}] lat={lat_ms}ms | rx={m.get('bytes_rx',0)} | cpu={m.get('cpu_pct',0)}%", flush=True)
            except Exception as e:
                print(f"[{now}] ERRO UDP: {e}", flush=True)

            if time.time() - last_save >= SAVE_INTERVAL:
                save(start_time, latencies, samples)
                last_save = time.time()
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        save(start_time, latencies, samples)

if __name__ == "__main__":
    main()
