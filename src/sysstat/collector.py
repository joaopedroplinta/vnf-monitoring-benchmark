#!/usr/bin/python3
"""
Coletor sysstat — TCC Gerenciamento de Rede
Métricas: CPU (%), Memória RSS, Latência, Bytes TX/RX, Conexões
Usa: psutil + ss (socket statistics) para monitorar a porta 9999
"""

import time, os, json, subprocess
from datetime import datetime
import psutil

TARGET_PORT   = 9999
SAVE_INTERVAL = 10
RESULTS_PATH  = "/app/results/sysstat_results.json"
os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_connections_on_port():
    """Retorna lista de conexões ativas na porta 9999 via psutil."""
    conns = []
    for c in psutil.net_connections(kind="tcp"):
        if c.laddr and c.laddr.port == TARGET_PORT:
            conns.append(c)
        elif c.raddr and c.raddr.port == TARGET_PORT:
            conns.append(c)
    return conns

def get_process_metrics(pid):
    """Retorna CPU % e memória RSS de um processo pelo PID."""
    try:
        p = psutil.Process(pid)
        cpu = p.cpu_percent(interval=0.1)
        mem = p.memory_info().rss / (1024 * 1024)  # MB
        return cpu, mem
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0, 0.0

def get_net_io():
    """Retorna bytes TX e RX acumulados da interface de rede principal."""
    net = psutil.net_io_counters()
    return net.bytes_sent, net.bytes_recv

def measure_latency():
    """Mede latência de conexão à porta 9999 via socket Python."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        t0 = time.time_ns()
        s.connect(("127.0.0.1", TARGET_PORT))
        lat_ms = (time.time_ns() - t0) / 1e6
        s.close()
        return round(lat_ms, 4)
    except Exception:
        return None

# ─── Coletor principal ────────────────────────────────────────────────────────

def collect():
    data = {
        "collector":      "sysstat",
        "timestamp":      datetime.utcnow().isoformat(),
        "duration_s":     0,
        "connections":    0,
        "bytes_tx":       0,
        "bytes_rx":       0,
        "latency_avg_ms": 0,
        "latency_max_ms": 0,
        "latency_min_ms": 0,
        "cpu_avg_pct":    0,
        "mem_avg_mb":     0,
        "samples":        [],
    }

    start_time   = time.time()
    net_start_tx, net_start_rx = get_net_io()

    cpu_samples  = []
    mem_samples  = []
    lat_samples  = []
    conn_set     = set()

    print("=" * 60)
    print("  📡 Coletor sysstat — porta 9999")
    print("  Métricas: CPU · Memória · Latência · Bytes · Conexões")
    print("=" * 60)

    try:
        while True:
            now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            # Conexões ativas
            conns = get_connections_on_port()
            for c in conns:
                if c.pid:
                    conn_set.add(c.pid)

            # Métricas dos processos conectados
            cpu_total, mem_total, proc_count = 0.0, 0.0, 0
            for c in conns:
                if c.pid:
                    cpu, mem = get_process_metrics(c.pid)
                    cpu_total += cpu
                    mem_total += mem
                    proc_count += 1

            avg_cpu = round(cpu_total / proc_count, 2) if proc_count else 0.0
            avg_mem = round(mem_total / proc_count, 2) if proc_count else 0.0

            if avg_cpu > 0: cpu_samples.append(avg_cpu)
            if avg_mem > 0: mem_samples.append(avg_mem)

            # Latência
            lat = measure_latency()
            if lat is not None:
                lat_samples.append(lat)

            # Bytes acumulados
            net_tx, net_rx = get_net_io()
            bytes_tx = net_tx - net_start_tx
            bytes_rx = net_rx - net_start_rx

            sample = {
                "time":       now,
                "connections": len(conns),
                "cpu_pct":    avg_cpu,
                "mem_mb":     avg_mem,
                "latency_ms": lat or 0,
                "bytes_tx":   bytes_tx,
                "bytes_rx":   bytes_rx,
            }
            data["samples"].append(sample)

            print(f"[{now}] conns={len(conns)} cpu={avg_cpu}% "
                  f"mem={avg_mem}MB lat={lat or '?'}ms "
                  f"TX={bytes_tx}B RX={bytes_rx}B")

            # Salva periodicamente
            if len(data["samples"]) % (SAVE_INTERVAL) == 0:
                _flush(data, start_time, conn_set,
                       cpu_samples, mem_samples, lat_samples,
                       bytes_tx, bytes_rx)

            time.sleep(1)

    except KeyboardInterrupt:
        net_tx, net_rx = get_net_io()
        _flush(data, start_time, conn_set,
               cpu_samples, mem_samples, lat_samples,
               net_tx - net_start_tx, net_rx - net_start_rx)
        print("\n[!] Coletor sysstat encerrado.")

def _flush(data, start_time, conn_set, cpu_s, mem_s, lat_s, tx, rx):
    data.update({
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
    })
    with open(RESULTS_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n💾 Resultado salvo: {RESULTS_PATH}")
    print(f"   Conexões:{data['connections']} | "
          f"TX:{data['bytes_tx']}B | RX:{data['bytes_rx']}B | "
          f"Lat:{data['latency_avg_ms']}ms | "
          f"CPU:{data['cpu_avg_pct']}% | Mem:{data['mem_avg_mb']}MB\n")

if __name__ == "__main__":
    collect()
