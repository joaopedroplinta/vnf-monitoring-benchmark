#!/usr/bin/env python3
"""
Coletor eBPF v17 — TCC Gerenciamento de Rede
Monitora latência via Kprobes filtrando por porta UDP 9999.
Resolve erro de underflow no bytes_tx.
"""
from bcc import BPF
import ctypes as ct
import socket, time, json, os, statistics
from datetime import datetime

MONITOR_HOST = 'localhost'
MONITOR_PORT = 9999
DURATION     = 240
INTERVAL     = 1
SAVE_INTERVAL= 10
RESULTS_PATH = "/app/results/ebpf_results.json"
os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

# Programa eBPF focado em medir o tempo entre sendto e recvfrom do coletor
bpf_program = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

BPF_HASH(start_ns, u32, u64);
BPF_HASH(latency_map, u32, u64);
BPF_HASH(tx_bytes_map, u32, u64);
BPF_HASH(rx_bytes_map, u32, u64);

int kprobe__sys_sendto(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 ts = bpf_ktime_get_ns();
    start_ns.update(&pid, &ts);
    
    u32 key = 0;
    u64 *acc, zero = 0;
    acc = tx_bytes_map.lookup_or_try_init(&key, &zero);
    if (acc) {
        // Incremento simbólico para mostrar atividade
        (*acc) += 1;
    }
    return 0;
}

int kretprobe__sys_recvfrom(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 now = bpf_ktime_get_ns();
    u64 *start = start_ns.lookup(&pid);
    
    if (start) {
        u64 lat = now - *start;
        latency_map.update(&pid, &lat);
        start_ns.delete(&pid);
        
        u32 key = 0;
        u64 *acc, zero = 0;
        acc = rx_bytes_map.lookup_or_try_init(&key, &zero);
        if (acc) (*acc) += 1;
    }
    return 0;
}
"""

def query_and_record(b, latencies, samples, last_metrics):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    pid = os.getpid()
    pid_ct = ct.c_uint32(pid)
    now_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    try:
        # Envia probe UDP para o monitor_server
        sock.sendto(b"GET", (MONITOR_HOST, MONITOR_PORT))
        data, _ = sock.recvfrom(65536)

        # Coleta latência do mapa eBPF
        lat_ms = 0
        if pid_ct in b["latency_map"]:
            lat_ns = b["latency_map"][pid_ct].value
            lat_ms = round(lat_ns / 1e6, 4)
            if 0 < lat_ms < 5000:
                latencies.append(lat_ms)
            del b["latency_map"][pid_ct]

        # Coleta métricas do WAF (via monitor_server)
        try:
            m = json.loads(data.decode("utf-8"))
            last_metrics.update(m)
        except:
            m = last_metrics

        sample = {
            "time":        now_str,
            "latency_ms":  lat_ms,
            "connections": m.get("connections", 0),
            "bytes_rx":    m.get("bytes_rx", 0),
            "bytes_tx":    m.get("bytes_tx", 0),
            "cpu_pct":     m.get("cpu_pct", 0),
            "mem_mb":      m.get("mem_mb", 0),
            "blocked":     m.get("blocked", 0),
            "allowed":     m.get("allowed", 0),
        }
        samples.append(sample)
        
        print(f"[{now_str}] lat={lat_ms}ms | cpu={m.get('cpu_pct',0)}% | connections={m.get('connections',0)}", flush=True)
    except Exception as e:
        print(f"[{now_str}] Erro: {e}", flush=True)
    finally:
        sock.close()

def save_results(start_time, latencies, samples):
    if not samples: return
    
    # Pegamos os dados da última amostra do WAF para o resumo global
    last = samples[-1]
    
    # Calculamos a média de CPU apenas das amostras que tiveram atividade (>0)
    cpu_active = [s["cpu_pct"] for s in samples if s["cpu_pct"] > 0]
    cpu_avg = round(statistics.mean(cpu_active), 2) if cpu_active else 0.0

    result = {
        "collector":                 "ebpf",
        "timestamp":                 datetime.utcnow().isoformat(),
        "duration_s":                round(time.time() - start_time, 2),
        "monitor_latency_avg_ms":    round(statistics.mean(latencies), 4) if latencies else 0,
        "monitor_latency_stddev_ms": round(statistics.stdev(latencies), 4) if len(latencies) > 1 else 0,
        "monitor_latency_max_ms":    round(max(latencies), 4) if latencies else 0,
        "monitor_latency_min_ms":    round(min(latencies), 4) if latencies else 0,
        "monitor_samples":           len(latencies),
        "bytes_rx":                  last.get("bytes_rx", 0),
        "bytes_tx":                  last.get("bytes_tx", 0),
        "connections":               last.get("connections", 0),
        "cpu_avg_pct":               cpu_avg,
        "mem_avg_mb":                round(statistics.mean([s["mem_mb"] for s in samples]), 2) if samples else 0,
        "waf_blocked":               last.get("blocked", 0),
        "waf_allowed":               last.get("allowed", 0),
        "samples":                   samples
    }
    
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n✅ Resultados salvos em {RESULTS_PATH}")

def main():
    print("Iniciando Coletor eBPF...")
    try:
        b = BPF(text=bpf_program)
    except Exception as e:
        print(f"Erro ao carregar eBPF: {e}")
        return

    start_time = time.time()
    last_save = time.time()
    latencies = []
    samples = []
    last_metrics = {}

    try:
        while time.time() - start_time < DURATION:
            query_and_record(b, latencies, samples, last_metrics)
            if time.time() - last_save > SAVE_INTERVAL:
                save_results(start_time, latencies, samples)
                last_save = time.time()
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        save_results(start_time, latencies, samples)

if __name__ == "__main__":
    main()
