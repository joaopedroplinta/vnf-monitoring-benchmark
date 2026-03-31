#!/usr/bin/python3
"""
Coletor Prometheus — TCC Gerenciamento de Rede
Expõe métricas em :8000/metrics (formato Prometheus)
E salva snapshot em results/prometheus_results.json para comparação
Porta monitorada: 9999
"""

import time, os, json, socket, threading
from datetime import datetime
from prometheus_client import (
    start_http_server, Gauge, Counter, Histogram, REGISTRY
)
import psutil

TARGET_PORT   = 9999
RESULTS_PATH  = "/app/results/prometheus_results.json"
SCRAPE_INTERVAL = 2
SAVE_INTERVAL   = 10
DURATION        = 480  # 8 minutos
os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

# ─── Definição das métricas Prometheus ───────────────────────────────────────

cpu_gauge      = Gauge("socket_cpu_percent",
                       "CPU % dos processos conectados na porta 9999")
mem_gauge      = Gauge("socket_mem_mb",
                       "Memória RSS (MB) dos processos na porta 9999")
latency_gauge  = Gauge("socket_latency_ms",
                       "Latência de conexão TCP à porta 9999 (ms)")
conn_gauge     = Gauge("socket_connections_total",
                       "Conexões ativas na porta 9999")
bytes_tx_gauge = Gauge("socket_bytes_tx_total",
                       "Bytes enviados desde o início da coleta")
bytes_rx_gauge = Gauge("socket_bytes_rx_total",
                       "Bytes recebidos desde o início da coleta")

latency_hist = Histogram("socket_latency_histogram_ms",
                         "Histograma de latência TCP (ms)",
                         buckets=[0.1, 0.5, 1, 2, 5, 10, 20, 50, 100])

# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_connections():
    conns = []
    for c in psutil.net_connections(kind="tcp"):
        if (c.laddr and c.laddr.port == TARGET_PORT) or \
           (c.raddr and c.raddr.port == TARGET_PORT):
            conns.append(c)
    return conns

def get_process_metrics(pid):
    try:
        p   = psutil.Process(pid)
        cpu = p.cpu_percent(interval=0.1)
        mem = p.memory_info().rss / (1024 * 1024)
        return cpu, mem
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0, 0.0

def measure_latency():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        t0 = time.time_ns()
        s.connect(("127.0.0.1", TARGET_PORT))
        lat = (time.time_ns() - t0) / 1e6
        s.close()
        return round(lat, 4)
    except Exception:
        return None

def get_net_io():
    n = psutil.net_io_counters()
    return n.bytes_sent, n.bytes_recv

# ─── Loop de coleta ───────────────────────────────────────────────────────────

def collect_loop():
    start_time              = time.time()
    net_start_tx, net_start_rx = get_net_io()
    last_save               = time.time()

    cpu_samples  = []
    mem_samples  = []
    lat_samples  = []
    conn_set     = set()
    samples      = []

    print("=" * 60)
    print("  📈 Coletor Prometheus — porta 9999")
    print("  Métricas expostas em http://localhost:8000/metrics")
    print("=" * 60)

    while time.time() - start_time < DURATION:
        now   = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        conns = get_connections()

        cpu_total, mem_total, proc_count = 0.0, 0.0, 0
        for c in conns:
            if c.pid:
                conn_set.add(c.pid)
                cpu, mem = get_process_metrics(c.pid)
                cpu_total += cpu
                mem_total += mem
                proc_count += 1

        avg_cpu = round(cpu_total / proc_count, 2) if proc_count else 0.0
        avg_mem = round(mem_total / proc_count, 2) if proc_count else 0.0
        lat     = measure_latency()
        net_tx, net_rx = get_net_io()
        bytes_tx = net_tx - net_start_tx
        bytes_rx = net_rx - net_start_rx

        cpu_gauge.set(avg_cpu)
        mem_gauge.set(avg_mem)
        conn_gauge.set(len(conns))
        bytes_tx_gauge.set(bytes_tx)
        bytes_rx_gauge.set(bytes_rx)
        if lat is not None:
            latency_gauge.set(lat)
            latency_hist.observe(lat)
            lat_samples.append(lat)

        if avg_cpu > 0: cpu_samples.append(avg_cpu)
        if avg_mem > 0: mem_samples.append(avg_mem)

        sample = {
            "time":        now,
            "connections": len(conns),
            "cpu_pct":     avg_cpu,
            "mem_mb":      avg_mem,
            "latency_ms":  lat or 0,
            "bytes_tx":    bytes_tx,
            "bytes_rx":    bytes_rx,
        }
        samples.append(sample)

        print(f"[{now}] conns={len(conns)} cpu={avg_cpu}% "
              f"mem={avg_mem}MB lat={lat or '?'}ms "
              f"TX={bytes_tx}B RX={bytes_rx}B")

        if time.time() - last_save >= SAVE_INTERVAL:
            _save(start_time, conn_set, cpu_samples, mem_samples,
                  lat_samples, bytes_tx, bytes_rx, samples)
            last_save = time.time()

        time.sleep(SCRAPE_INTERVAL)

def _save(start_time, conn_set, cpu_s, mem_s, lat_s, tx, rx, samples):
    snapshot = {
        "collector":      "prometheus",
        "timestamp":      datetime.utcnow().isoformat(),
        "duration_s":     round(time.time() - start_time, 2),
        "connections":    len(conn_set),
        "bytes_tx":       tx,
        "bytes_rx":       rx,
        "latency_avg_ms": round(sum(lat_s)/len(lat_s), 4) if lat_s else 0,
        "latency_max_ms": round(max(lat_s), 4)            if lat_s else 0,
        "latency_min_ms": round(min(lat_s), 4)            if lat_s else 0,
        "cpu_avg_pct":    round(sum(cpu_s)/len(cpu_s), 2) if cpu_s else 0,
        "mem_avg_mb":     round(sum(mem_s)/len(mem_s), 2) if mem_s else 0,
        "samples":        samples[-50:],
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"\n💾 Resultado salvo: {RESULTS_PATH}")
    print(f"   Conexões:{snapshot['connections']} | "
          f"TX:{snapshot['bytes_tx']}B | RX:{snapshot['bytes_rx']}B | "
          f"Lat:{snapshot['latency_avg_ms']}ms | "
          f"CPU:{snapshot['cpu_avg_pct']}% | Mem:{snapshot['mem_avg_mb']}MB\n")

def main():
    start_http_server(8000)
    print("✅ Servidor Prometheus iniciado em :8000/metrics")
    try:
        collect_loop()
    except KeyboardInterrupt:
        print("\n[!] Coletor Prometheus encerrado.")

if __name__ == "__main__":
    main()