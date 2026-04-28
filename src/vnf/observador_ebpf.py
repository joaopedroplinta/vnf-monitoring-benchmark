#!/usr/bin/env python3
"""
Observador eBPF — TCC Gerenciamento de Rede
Coleta bytes RX/TX via kprobes BCC (sport=8080) + CPU/mem do processo WAF via psutil.
Serve métricas via UDP :9999.
Requer: privileged=true, pid=host.
"""
from bcc import BPF
import ctypes as ct
import socket, json, os
import psutil

HOST = '0.0.0.0'
PORT = 9999
_WAF_METRICS_PATH = os.environ.get("WAF_METRICS_PATH", "/app/results/waf_metrics.json")


def _read_waf_metrics() -> dict:
    try:
        with open(_WAF_METRICS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}

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

_self_proc = psutil.Process()
_waf_proc = None

def _find_waf():
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if 'waf.py' in ' '.join(proc.info['cmdline'] or []):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def get_waf_metrics():
    global _waf_proc
    try:
        if _waf_proc is None or not _waf_proc.is_running():
            _waf_proc = _find_waf()
        if _waf_proc:
            return (
                round(_waf_proc.cpu_percent(interval=None), 2),
                round(_waf_proc.memory_info().rss / 1024 / 1024, 2),
            )
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        _waf_proc = None
    return 0.0, 0.0

def main():
    print("=" * 55)
    print("  Observador eBPF — kprobes sport=8080 + psutil WAF")
    print("=" * 55)

    b = BPF(text=bpf_program)
    print("BPF carregado. Monitorando sport=8080.", flush=True)

    # Warm-up: primeira chamada cpu_percent sempre retorna 0
    _waf_proc = _find_waf()
    if _waf_proc:
        _waf_proc.cpu_percent(interval=None)
    _self_proc.cpu_percent(interval=None)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"Observador eBPF UDP escutando em {HOST}:{PORT}", flush=True)

    while True:
        try:
            _, addr = sock.recvfrom(256)
            rx = b["net_stats"][ct.c_uint32(0)].value
            tx = b["net_stats"][ct.c_uint32(1)].value
            cpu, mem = get_waf_metrics()
            wm = _read_waf_metrics()
            resp = json.dumps({
                "bytes_rx":          rx,
                "bytes_tx":          tx,
                "cpu_pct":           cpu,
                "mem_mb":            mem,
                "collector_cpu_pct": round(_self_proc.cpu_percent(interval=None), 2),
                "collector_mem_mb":  round(_self_proc.memory_info().rss / 1024 / 1024, 2),
                "inspect_count":     wm.get("inspect_count", 0),
                "inspect_avg_ms":    wm.get("inspect_avg_ms", 0.0),
                "inspect_min_ms":    wm.get("inspect_min_ms", 0.0),
                "inspect_max_ms":    wm.get("inspect_max_ms", 0.0),
            }).encode("utf-8")
            sock.sendto(resp, addr)
        except Exception as e:
            print(f"[ERRO] {e}")

if __name__ == "__main__":
    main()
