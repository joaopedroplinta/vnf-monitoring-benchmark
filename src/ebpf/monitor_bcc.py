#!/usr/bin/env python3
"""
Coletor eBPF v23 — TCC Gerenciamento de Rede
Latência medida no userspace (kprobe udp_recvmsg não dispara no kernel 6.12+).
Bytes RX/TX via kprobes TCP contando APENAS o lado servidor do WAF (sport=8080),
evitando a dupla contagem que ocorre no tráfego loopback.

Por que apenas sport=8080?
  No loopback, cada pacote passa pelo kernel dos dois lados (cliente e servidor).
  Contar sport OU dport == 8080 duplica o mesmo dado. Contar somente sport=8080
  garante que medimos exatamente os bytes que o processo WAF leu (RX) e escreveu (TX).
"""
from bcc import BPF
import ctypes as ct
import socket, time, json, os, statistics
from datetime import datetime

MONITOR_HOST  = '127.0.0.1'
MONITOR_PORT  = 9999
DURATION      = 60
INTERVAL      = 1
SAVE_INTERVAL = 10
RESULTS_PATH  = "/app/results/ebpf_results.json"
os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

# Programa eBPF v23
# - tcp_sendmsg    : conta TX apenas quando sport==8080 (WAF enviando resposta)
# - tcp_cleanup_rbuf: conta RX apenas quando sport==8080 (WAF lendo requisição)
# Desta forma não conta o lado do cliente, evitando dupla contagem no loopback.
bpf_program = """
/* Forward declaration para contornar erro struct bpf_wq em kernels 6.10+ */
struct bpf_wq {
    unsigned long long :64;
    unsigned long long :64;
} __attribute__((aligned(8)));

#include <uapi/linux/ptrace.h>
#include <net/sock.h>
#include <bcc/proto.h>
#include <linux/tcp.h>

BPF_ARRAY(net_stats, u64, 2); // 0: RX, 1: TX

// WAF TX: WAF enviando resposta ao cliente (socket do servidor, sport=8080)
int kprobe__tcp_sendmsg(struct pt_regs *ctx, struct sock *sk, struct msghdr *msg, size_t size) {
    u16 sport = sk->__sk_common.skc_num;
    if (sport == 8080) {
        u32 key = 1;
        u64 *val = net_stats.lookup(&key);
        if (val) *val += size;
    }
    return 0;
}

// WAF RX: WAF lendo requisição do cliente (socket do servidor, sport=8080)
int kprobe__tcp_cleanup_rbuf(struct pt_regs *ctx, struct sock *sk, int copied) {
    if (copied <= 0) return 0;
    u16 sport = sk->__sk_common.skc_num;
    if (sport == 8080) {
        u32 key = 0;
        u64 *val = net_stats.lookup(&key);
        if (val) *val += (u64)copied;
    }
    return 0;
}
"""

def query_and_record(b, latencies, samples, last_metrics):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.5)
    now_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    try:
        # Latência medida no userspace (kprobe udp_recvmsg não funciona no kernel 6.12+)
        t0 = time.time()
        sock.sendto(b"GET", (MONITOR_HOST, MONITOR_PORT))
        data, _ = sock.recvfrom(65536)
        lat_ms = round((time.time() - t0) * 1000, 4)

        if 0 < lat_ms < 2000:
            latencies.append(lat_ms)

        # Bytes acumulados pelo WAF (lado servidor, sport=8080)
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
    print(f"  Coletor eBPF v23 — Latencia userspace + kprobe sport=8080")
    print("=" * 55)

    try:
        b = BPF(text=bpf_program)
        print(f"BPF carregado. Monitorando sport=8080 (WAF server side).", flush=True)
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
