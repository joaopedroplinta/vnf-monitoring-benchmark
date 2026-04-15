#!/usr/bin/env python3
"""
Coletor sysstat — TCC Gerenciamento de Rede (v2)
Acumula TODAS as amostras e latências brutas.
Recalcula média e desvio padrão com todos os dados ao final.
"""
import socket, time, json, os, statistics
from datetime import datetime

MONITOR_HOST  = 'localhost'
MONITOR_PORT  = 9999
DURATION      = int(os.environ.get("DURATION", 60))
INTERVAL      = 1
SAVE_INTERVAL = 10
RESULTS_PATH  = "/app/results/sysstat_results.json"
os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

def query_monitor() -> tuple[float, dict]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    try:
        t0 = time.time_ns()
        sock.sendto(b"GET", (MONITOR_HOST, MONITOR_PORT))
        data, _ = sock.recvfrom(65536)
        latency_ms = (time.time_ns() - t0) / 1e6
        return round(latency_ms, 4), json.loads(data.decode("utf-8"))
    finally:
        sock.close()

def get_system_network_bytes(interface="lo"):
    """Lê bytes RX/TX diretamente do kernel via /proc/net/dev."""
    try:
        with open("/proc/net/dev", "r") as f:
            lines = f.readlines()
            for line in lines:
                if interface in line:
                    parts = line.split()
                    rx = int(parts[1])
                    tx = int(parts[9])
                    return rx, tx
    except Exception:
        pass
    return 0, 0

def collect():
    print("=" * 55)
    print("  📡 Coletor sysstat — Monitor UDP porta 9999")
    print("  Acumulando todas as amostras e latências brutas")
    print("  Monitorando rede via /proc/net/dev (lo)")
    print("=" * 55)

    start_time   = time.time()
    last_save    = time.time()
    latencies    = []   # TODAS as latências brutas acumuladas
    samples      = []   # TODOS os snapshots acumulados
    last_metrics = {}

    # Ponto de partida para calcular o delta, se necessário, mas vamos manter o acumulado
    # para ser comparável com o WAF.
    start_rx, start_tx = get_system_network_bytes()

    while time.time() - start_time < DURATION:
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        try:
            lat_ms, metrics = query_monitor()
            latencies.append(lat_ms)
            last_metrics = metrics
            
            # Pega bytes reais do sistema (lo — tráfego WAF via loopback)
            sys_rx, sys_tx = get_system_network_bytes()

            sample = {
                "time":        now,
                "latency_ms":  lat_ms,
                "connections": metrics.get("connections", 0),
                "bytes_rx":    sys_rx - start_rx, # Tráfego medido DURANTE o teste
                "bytes_tx":    sys_tx - start_tx,
                "cpu_pct":     metrics.get("cpu_pct", 0),
                "mem_mb":      metrics.get("mem_mb", 0),
                "blocked":     metrics.get("blocked", 0),
                "allowed":     metrics.get("allowed", 0),
            }
            samples.append(sample)  # acumula todos, sem limite

            print(f"[{now}] lat={lat_ms}ms | "
                  f"conns={metrics.get('connections',0)} | "
                  f"sys_rx={sample['bytes_rx']} | "
                  f"block={metrics.get('blocked',0)}")
        except Exception as e:
            print(f"[{now}] ERRO UDP: {e}")

        if time.time() - last_save >= SAVE_INTERVAL:
            _flush(start_time, latencies, samples, last_metrics)
            last_save = time.time()

        time.sleep(INTERVAL)

    _flush(start_time, latencies, samples, last_metrics)
    print("\n✅ Coleta sysstat encerrada.")

def _flush(start_time, latencies, samples, last_metrics):
    if not samples: return
    last_sample = samples[-1]

    cpu_values = [s["cpu_pct"] for s in samples if s.get("cpu_pct") is not None]
    mem_values = [s["mem_mb"]  for s in samples if s.get("mem_mb")  is not None]

    result = {
        "collector":                 "sysstat",
        "timestamp":                 datetime.utcnow().isoformat(),
        "duration_s":                round(time.time() - start_time, 2),
        "monitor_latency_avg_ms":    round(statistics.mean(latencies), 4)   if latencies else 0,
        "monitor_latency_stddev_ms": round(statistics.stdev(latencies), 4)  if len(latencies) > 1 else 0,
        "monitor_latency_max_ms":    round(max(latencies), 4)               if latencies else 0,
        "monitor_latency_min_ms":    round(min(latencies), 4)               if latencies else 0,
        "monitor_samples":           len(latencies),
        "latencies_raw":             latencies,
        "connections":               last_metrics.get("connections", 0),
        "bytes_rx":                  last_sample["bytes_rx"],
        "bytes_tx":                  last_sample["bytes_tx"],
        "cpu_avg_pct":               round(statistics.mean(cpu_values), 2) if cpu_values else 0,
        "mem_avg_mb":                round(statistics.mean(mem_values), 2) if mem_values else 0,
        "waf_blocked":               last_metrics.get("blocked", 0),
        "waf_allowed":               last_metrics.get("allowed", 0),
        "samples":                   samples,
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n💾 sysstat salvo | "
          f"lat_avg={result['monitor_latency_avg_ms']}ms | "
          f"stddev={result['monitor_latency_stddev_ms']}ms | "
          f"n={result['monitor_samples']}\n")

if __name__ == "__main__":
    collect()