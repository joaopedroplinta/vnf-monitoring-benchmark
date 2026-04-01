#!/usr/bin/env python3
"""
Coletor Prometheus — TCC Gerenciamento de Rede (v2)
Acumula TODAS as amostras e latências brutas.
"""
import socket, time, json, os, statistics
from datetime import datetime
from prometheus_client import start_http_server, Gauge, Histogram

MONITOR_HOST  = 'localhost'
MONITOR_PORT  = 9999
DURATION      = 240
INTERVAL      = 1
SAVE_INTERVAL = 10
RESULTS_PATH  = "/app/results/prometheus_results.json"
os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

monitor_latency = Gauge("monitor_latency_ms",  "Tempo de monitoramento UDP (ms)")
monitor_hist    = Histogram("monitor_latency_histogram_ms", "Histograma latência monitoramento",
                            buckets=[0.1, 0.5, 1, 2, 5, 10, 20, 50, 100])
waf_connections = Gauge("waf_connections_total", "Conexões ao WAF")
waf_bytes_rx    = Gauge("waf_bytes_rx_total",    "Bytes recebidos pelo WAF")
waf_bytes_tx    = Gauge("waf_bytes_tx_total",    "Bytes enviados pelo WAF")
waf_cpu         = Gauge("waf_cpu_percent",       "CPU do WAF (%)")
waf_mem         = Gauge("waf_mem_mb",            "Memória do WAF (MB)")
waf_blocked     = Gauge("waf_blocked_total",     "Requisições bloqueadas")
waf_allowed     = Gauge("waf_allowed_total",     "Requisições permitidas")

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

def collect_loop():
    start_time = time.time()
    last_save  = time.time()
    latencies  = []   # TODAS as latências brutas acumuladas
    samples    = []   # TODOS os snapshots acumulados
    last_m     = {}

    print("=" * 55)
    print("  📈 Coletor Prometheus — Monitor UDP porta 9999")
    print("  Acumulando todas as amostras e latências brutas")
    print("=" * 55)

    while time.time() - start_time < DURATION:
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        try:
            lat_ms, m = query_monitor()
            latencies.append(lat_ms)
            last_m = m

            monitor_latency.set(lat_ms)
            monitor_hist.observe(lat_ms)
            waf_connections.set(m.get("connections", 0))
            waf_bytes_rx.set(m.get("bytes_rx", 0))
            waf_bytes_tx.set(m.get("bytes_tx", 0))
            waf_cpu.set(m.get("cpu_pct", 0))
            waf_mem.set(m.get("mem_mb", 0))
            waf_blocked.set(m.get("blocked", 0))
            waf_allowed.set(m.get("allowed", 0))

            sample = {
                "time":        now,
                "latency_ms":  lat_ms,
                "connections": m.get("connections", 0),
                "bytes_rx":    m.get("bytes_rx", 0),
                "bytes_tx":    m.get("bytes_tx", 0),
                "cpu_pct":     m.get("cpu_pct", 0),
                "mem_mb":      m.get("mem_mb", 0),
                "blocked":     m.get("blocked", 0),
                "allowed":     m.get("allowed", 0),
            }
            samples.append(sample)  # acumula todos

            print(f"[{now}] lat={lat_ms}ms | cpu={m.get('cpu_pct',0)}% | block={m.get('blocked',0)}")
        except Exception as e:
            print(f"[{now}] ERRO UDP: {e}")

        if time.time() - last_save >= SAVE_INTERVAL:
            _save(start_time, latencies, samples, last_m)
            last_save = time.time()

        time.sleep(INTERVAL)

    _save(start_time, latencies, samples, last_m)

def _save(start_time, latencies, samples, m):
    result = {
        "collector":                 "prometheus",
        "timestamp":                 datetime.utcnow().isoformat(),
        "duration_s":                round(time.time() - start_time, 2),
        "monitor_latency_avg_ms":    round(statistics.mean(latencies), 4)  if latencies else 0,
        "monitor_latency_stddev_ms": round(statistics.stdev(latencies), 4) if len(latencies) > 1 else 0,
        "monitor_latency_max_ms":    round(max(latencies), 4)              if latencies else 0,
        "monitor_latency_min_ms":    round(min(latencies), 4)              if latencies else 0,
        "monitor_samples":           len(latencies),
        "latencies_raw":             latencies,  # todas as latências brutas
        "connections":               m.get("connections", 0),
        "bytes_rx":                  m.get("bytes_rx", 0),
        "bytes_tx":                  m.get("bytes_tx", 0),
        "cpu_avg_pct":               m.get("cpu_pct", 0),
        "mem_avg_mb":                m.get("mem_mb", 0),
        "waf_blocked":               m.get("blocked", 0),
        "waf_allowed":               m.get("allowed", 0),
        "samples":                   samples,  # todos os snapshots
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n💾 prometheus salvo | lat_avg={result['monitor_latency_avg_ms']}ms | "
          f"stddev={result['monitor_latency_stddev_ms']}ms | n={result['monitor_samples']}\n")

def main():
    start_http_server(8000)
    print("✅ Prometheus HTTP em :8000/metrics")
    collect_loop()

if __name__ == "__main__":
    main()