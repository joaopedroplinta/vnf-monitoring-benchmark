#!/usr/bin/env python3
"""
Coletor eBPF v15 — TCC Gerenciamento de Rede
Acumula TODAS as amostras e latências brutas.
Recalcula média e desvio padrão com todos os dados.
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

bpf_program = """
#include <uapi/linux/ptrace.h>

#define MONITOR_PORT 9999

BPF_HASH(send_ts,     u32, u64);
BPF_HASH(latency_map, u32, u64);
BPF_HASH(rx_bytes,    u32, u64);
BPF_HASH(tx_bytes,    u32, u64);
BPF_HASH(my_tgid,     u32, u8);

TRACEPOINT_PROBE(syscalls, sys_enter_sendto) {
    u32 tgid = bpf_get_current_pid_tgid() >> 32;
    u8 *ok = my_tgid.lookup(&tgid);
    if (!ok) return 0;
    u64 ts = bpf_ktime_get_ns();
    send_ts.update(&tgid, &ts);
    u32 key = 0; u64 zero = 0, *acc;
    acc = tx_bytes.lookup_or_try_init(&key, &zero);
    if (acc && args->len > 0) (*acc) += args->len;
    return 0;
}

TRACEPOINT_PROBE(syscalls, sys_exit_recvfrom) {
    if (args->ret <= 0) return 0;
    u32 tgid = bpf_get_current_pid_tgid() >> 32;
    u8 *ok = my_tgid.lookup(&tgid);
    if (!ok) return 0;
    u64 now = bpf_ktime_get_ns();
    u64 zero = 0, *acc, *start;
    u32 key = 0;
    acc = rx_bytes.lookup_or_try_init(&key, &zero);
    if (acc) (*acc) += (u64)args->ret;
    start = send_ts.lookup(&tgid);
    if (start && now > *start) {
        u64 lat = now - *start;
        latency_map.update(&tgid, &lat);
        send_ts.delete(&tgid);
    }
    return 0;
}
"""

b = None

def query_and_record(tgid_ct, latencies, samples, last_metrics):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    try:
        sock.sendto(b"GET", (MONITOR_HOST, MONITOR_PORT))
        data, _ = sock.recvfrom(65536)

        try:
            lat_ns = b["latency_map"][tgid_ct].value
            lat_ms = round(lat_ns / 1e6, 4)
            if 0 < lat_ms < 5000:
                latencies.append(lat_ms)  # acumula todas
            b["latency_map"].clear()
        except KeyError:
            lat_ms = 0

        try:
            m = json.loads(data.decode("utf-8"))
            last_metrics.update(m)
        except Exception:
            m = last_metrics

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

        print(f"[{now}] lat={lat_ms}ms | "
              f"cpu={m.get('cpu_pct',0)}% | "
              f"block={m.get('blocked',0)}", flush=True)
    except Exception as e:
        print(f"[{now}] ERRO UDP: {e}", flush=True)
    finally:
        sock.close()

def save_results(start_time, latencies, samples, last_metrics):
    try:
        tx = b["tx_bytes"][ct.c_uint32(0)].value
    except KeyError:
        tx = 0
    try:
        rx = b["rx_bytes"][ct.c_uint32(0)].value
    except KeyError:
        rx = 0

    result = {
        "collector":                 "ebpf",
        "timestamp":                 datetime.utcnow().isoformat(),
        "duration_s":                round(time.time() - start_time, 2),
        # Calculado com TODAS as latências acumuladas
        "monitor_latency_avg_ms":    round(statistics.mean(latencies), 4)  if latencies else 0,
        "monitor_latency_stddev_ms": round(statistics.stdev(latencies), 4) if len(latencies) > 1 else 0,
        "monitor_latency_max_ms":    round(max(latencies), 4)              if latencies else 0,
        "monitor_latency_min_ms":    round(min(latencies), 4)              if latencies else 0,
        "monitor_samples":           len(latencies),
        "latencies_raw":             latencies,  # todas as latências brutas
        "bytes_tx":                  tx,
        "bytes_rx":                  rx,
        "connections":               last_metrics.get("connections", 0),
        "cpu_avg_pct":               last_metrics.get("cpu_pct", 0),
        "mem_avg_mb":                last_metrics.get("mem_mb", 0),
        "waf_blocked":               last_metrics.get("blocked", 0),
        "waf_allowed":               last_metrics.get("allowed", 0),
        "samples":                   samples,  # todos os snapshots
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n💾 eBPF salvo | lat_avg={result['monitor_latency_avg_ms']}ms | "
          f"stddev={result['monitor_latency_stddev_ms']}ms | "
          f"n={result['monitor_samples']}\n")

def main():
    global b
    print("=" * 55)
    print(f"  🔍 Coletor eBPF v15 — Monitor UDP porta {MONITOR_PORT}")
    print(f"  Acumulando todas as amostras e latências brutas")
    print(f"  Duração: {DURATION//60} minutos")
    print("=" * 55)

    b = BPF(text=bpf_program)
    print("✅ BPF carregado", flush=True)

    my_tgid = os.getpid()
    b["my_tgid"][ct.c_uint32(my_tgid)] = ct.c_uint8(1)
    tgid_ct = ct.c_uint32(my_tgid)
    print(f"✅ TGID injetado: {my_tgid}", flush=True)

    start_time   = time.time()
    last_save    = time.time()
    latencies    = []
    samples      = []
    last_metrics = {}

    try:
        while time.time() - start_time < DURATION:
            query_and_record(tgid_ct, latencies, samples, last_metrics)

            if time.time() - last_save >= SAVE_INTERVAL:
                save_results(start_time, latencies, samples, last_metrics)
                last_save = time.time()

            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\n[!] Interrompido")
    finally:
        print("\n[✓] Salvando resultado final...")
        save_results(start_time, latencies, samples, last_metrics)
        print("[✓] Encerrado.")

if __name__ == "__main__":
    main()