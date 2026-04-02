#!/usr/bin/env python3
"""
Coletor eBPF v21 — TCC Gerenciamento de Rede
Monitoramento seletivo por portas (8080, 9999) para evitar discrepâncias.
"""
from bcc import BPF
import ctypes as ct
import socket, time, json, os, statistics
from datetime import datetime

MONITOR_HOST = '127.0.0.1'
MONITOR_PORT = 9999
DURATION     = 60
INTERVAL     = 1
SAVE_INTERVAL= 10
RESULTS_PATH = "/app/results/ebpf_results.json"
os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

# Programa eBPF v21 — Filtragem por Porta (TCP e UDP)
bpf_program = """
#include <uapi/linux/ptrace.h>
#include <net/sock.h>
#include <bcc/proto.h>
#include <linux/tcp.h>

BPF_HASH(start_ns, u32, u64);
BPF_HASH(latency_map, u32, u64);
BPF_ARRAY(net_stats, u64, 2); // 0: RX, 1: TX

// Função auxiliar para verificar portas de interesse
static inline bool is_target_port(u16 port) {
    return port == 8080 || port == 9999;
}

// 1. TCP Send (WAF TX)
int kprobe__tcp_sendmsg(struct pt_regs *ctx, struct sock *sk, struct msghdr *msg, size_t size) {
    u16 dport = sk->__sk_common.skc_dport;
    dport = ntohs(dport);
    
    if (is_target_port(dport)) {
        u32 key = 1; // TX
        u64 *val = net_stats.lookup(&key);
        if (val) *val += size;
    }
    return 0;
}

// 2. TCP Receive (WAF RX)
int kprobe__tcp_cleanup_rbuf(struct pt_regs *ctx, struct sock *sk, int copied) {
    if (copied <= 0) return 0;
    
    u16 sport = sk->__sk_common.skc_num;
    if (is_target_port(sport)) {
        u32 key = 0; // RX
        u64 *val = net_stats.lookup(&key);
        if (val) *val += (u64)copied;
    }
    return 0;
}

// 3. UDP Send (Monitor Probe TX)
int kprobe__udp_sendmsg(struct pt_regs *ctx, struct sock *sk, struct msghdr *msg, size_t len) {
    u16 dport = sk->__sk_common.skc_dport;
    dport = ntohs(dport);
    
    if (dport == 9999) {
        u32 key = 1; // TX
        u64 *val = net_stats.lookup(&key);
        if (val) *val += len;
        
        u32 pid = bpf_get_current_pid_tgid() >> 32;
        u64 ts = bpf_ktime_get_ns();
        start_ns.update(&pid, &ts);
    }
    return 0;
}

// 4. UDP Receive (Monitor Probe RX)
int kprobe__udp_recvmsg(struct pt_regs *ctx, struct sock *sk, struct msghdr *msg, size_t len) {
    u16 sport = sk->__sk_common.skc_num;
    if (sport == 9999) {
        u32 key = 0; // RX
        u64 *val = net_stats.lookup(&key);
        if (val) *val += len;

        u32 pid = bpf_get_current_pid_tgid() >> 32;
        u64 *start = start_ns.lookup(&pid);
        if (start) {
            u64 now = bpf_ktime_get_ns();
            u64 lat = now - *start;
            latency_map.update(&pid, &lat);
            start_ns.delete(&pid);
        }
    }
    return 0;
}
"""

def query_and_record(b, latencies, samples, last_metrics):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.5)
    pid = os.getpid()
    pid_ct = ct.c_uint32(pid)
    now_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    try:
        sock.sendto(b"GET", (MONITOR_HOST, MONITOR_PORT))
        data, _ = sock.recvfrom(65536)

        # 1. Latência do eBPF
        lat_ms = 0
        if pid_ct in b["latency_map"]:
            lat_ns = b["latency_map"][pid_ct].value
            lat_ms = round(lat_ns / 1e6, 4)
            if 0 < lat_ms < 2000:
                latencies.append(lat_ms)
            b["latency_map"].clear()

        # 2. Bytes RX/TX filtrados
        rx_bytes = b["net_stats"][ct.c_uint32(0)].value
        tx_bytes = b["net_stats"][ct.c_uint32(1)].value

        try:
            m = json.loads(data.decode("utf-8"))
            last_metrics.update(m)
        except:
            m = last_metrics

        sample = {
            "time":        now_str,
            "latency_ms":  lat_ms,
            "connections": m.get("connections", 0),
            "bytes_rx":    rx_bytes,
            "bytes_tx":    tx_bytes,
            "cpu_pct":     m.get("cpu_pct", 0),
            "mem_mb":      m.get("mem_mb", 0),
            "blocked":     m.get("blocked", 0),
            "allowed":     m.get("allowed", 0),
        }
        samples.append(sample)
        
        print(f"[{now_str}] lat={lat_ms}ms | rx={rx_bytes} | tx={tx_bytes} | cpu={m.get('cpu_pct',0)}%", flush=True)
    except Exception as e:
        print(f"[{now_str}] Erro UDP: {e}", flush=True)
    finally:
        sock.close()

def save_results(start_time, latencies, samples):
    if not samples: return
    last = samples[-1]
    cpu_avg = round(statistics.mean([s["cpu_pct"] for s in samples]), 2)

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
        "mem_avg_mb":                round(statistics.mean([s["mem_mb"] for s in samples]), 2),
        "waf_blocked":               last.get("blocked", 0),
        "waf_allowed":               last.get("allowed", 0),
        "samples":                   samples
    }
    
    with open(RESULTS_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n💾 eBPF salvo | lat_avg={result['monitor_latency_avg_ms']}ms | rx={result['bytes_rx']} | tx={result['bytes_tx']}")

def main():
    print("=" * 55)
    print(f"  🔍 Coletor eBPF v21 — Filtro Portas 8080, 9999")
    print("=" * 55)

    try:
        b = BPF(text=bpf_program)
        print(f"✅ BPF carregado. Monitorando tráfego do WAF e Monitor.", flush=True)
    except Exception as e:
        print(f"❌ Erro ao carregar eBPF: {e}")
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
