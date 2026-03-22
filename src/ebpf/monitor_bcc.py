#!/usr/bin/python3
"""
Coletor eBPF — TCC Gerenciamento de Rede
Métricas: CPU (%), Memória RSS, Latência, Bytes TX/RX, Conexões
Porta monitorada: 9999
"""

from bcc import BPF
import ctypes as ct
import time, os, json
from datetime import datetime

# ─── Programa eBPF ────────────────────────────────────────────────────────────
bpf_program = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>
#include <net/sock.h>
#include <net/inet_sock.h>
#include <bcc/proto.h>

#define TARGET_PORT 9999

struct event_t {
    u32  pid;
    u64  timestamp_ns;
    u64  latency_ns;
    u64  cpu_time_ns;
    u64  vm_rss_kb;
    u64  bytes_count;
    u16  dport;
    u8   event_type;   // 1=connect 2=send 3=recv
    char comm[16];
};

BPF_HASH(send_ts,  u32, u64);
BPF_HASH(conn_cnt, u16, u64);
BPF_HASH(bytes_tx, u32, u64);
BPF_HASH(bytes_rx, u32, u64);
BPF_PERF_OUTPUT(events);

static inline u64 get_rss_kb(void) {
    struct task_struct *t = (struct task_struct *)bpf_get_current_task();
    struct mm_struct *mm = NULL;
    u64 total_vm = 0;
    bpf_probe_read_kernel(&mm, sizeof(mm), &t->mm);
    if (!mm) return 0;
    bpf_probe_read_kernel(&total_vm, sizeof(total_vm), &mm->total_vm);
    return total_vm * 4;
}

static inline u64 get_cpu_ns(void) {
    struct task_struct *t = (struct task_struct *)bpf_get_current_task();
    u64 utime = 0, stime = 0;
    bpf_probe_read_kernel(&utime, sizeof(utime), &t->utime);
    bpf_probe_read_kernel(&stime, sizeof(stime), &t->stime);
    return utime + stime;
}

static inline void fill_base(struct event_t *e, u8 type) {
    e->pid          = bpf_get_current_pid_tgid() >> 32;
    e->timestamp_ns = bpf_ktime_get_ns();
    e->event_type   = type;
    e->cpu_time_ns  = get_cpu_ns();
    e->vm_rss_kb    = get_rss_kb();
    bpf_get_current_comm(&e->comm, sizeof(e->comm));
}

int trace_connect(struct pt_regs *ctx, struct sock *sk) {
    u16 dport = 0;
    bpf_probe_read_kernel(&dport, sizeof(dport), &sk->__sk_common.skc_dport);
    if (ntohs(dport) != TARGET_PORT) return 0;
    struct event_t e = {};
    fill_base(&e, 1);
    e.dport = TARGET_PORT;
    u16 port = TARGET_PORT;
    u64 zero = 0, *cnt;
    cnt = conn_cnt.lookup_or_try_init(&port, &zero);
    if (cnt) (*cnt)++;
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

int trace_send(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 ts  = bpf_ktime_get_ns();
    send_ts.update(&pid, &ts);
    u64 size = (u64)PT_REGS_PARM3(ctx);
    u64 zero = 0, *acc;
    acc = bytes_tx.lookup_or_try_init(&pid, &zero);
    if (acc) (*acc) += size;
    struct event_t e = {};
    fill_base(&e, 2);
    e.dport       = TARGET_PORT;
    e.bytes_count = size;
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

int trace_recv(struct pt_regs *ctx) {
    u32 pid    = bpf_get_current_pid_tgid() >> 32;
    u64 *start = send_ts.lookup(&pid);
    u64 size   = (u64)PT_REGS_PARM3(ctx);
    u64 zero   = 0, *acc;
    acc = bytes_rx.lookup_or_try_init(&pid, &zero);
    if (acc) (*acc) += size;
    struct event_t e = {};
    fill_base(&e, 3);
    e.dport       = TARGET_PORT;
    e.bytes_count = size;
    if (start) {
        e.latency_ns = bpf_ktime_get_ns() - *start;
        send_ts.delete(&pid);
    }
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}
"""

# ─── Estrutura Python ─────────────────────────────────────────────────────────
class Event(ct.Structure):
    _fields_ = [
        ("pid",          ct.c_uint32),
        ("timestamp_ns", ct.c_uint64),
        ("latency_ns",   ct.c_uint64),
        ("cpu_time_ns",  ct.c_uint64),
        ("vm_rss_kb",    ct.c_uint64),
        ("bytes_count",  ct.c_uint64),
        ("dport",        ct.c_uint16),
        ("event_type",   ct.c_uint8),
        ("comm",         ct.c_char * 16),
    ]

# ─── Acumuladores ─────────────────────────────────────────────────────────────
data = {
    "connections":  0,
    "bytes_tx":     0,
    "bytes_rx":     0,
    "latencies_ms": [],
    "cpu_pct":      [],
    "mem_mb":       [],
    "samples":      [],
}
start_time    = time.time()
last_save     = time.time()
SAVE_INTERVAL = 10
RESULTS_PATH  = "/app/results/ebpf_results.json"
os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

_prev_cpu_ns  = {}
_prev_wall_ns = {}

def save_results():
    global last_save
    lats = data["latencies_ms"]
    cpus = data["cpu_pct"]
    mems = data["mem_mb"]
    snapshot = {
        "collector":      "ebpf",
        "timestamp":      datetime.utcnow().isoformat(),
        "duration_s":     round(time.time() - start_time, 2),
        "connections":    data["connections"],
        "bytes_tx":       data["bytes_tx"],
        "bytes_rx":       data["bytes_rx"],
        "latency_avg_ms": round(sum(lats)/len(lats), 4) if lats else 0,
        "latency_max_ms": round(max(lats), 4)           if lats else 0,
        "latency_min_ms": round(min(lats), 4)           if lats else 0,
        "cpu_avg_pct":    round(sum(cpus)/len(cpus), 2) if cpus else 0,
        "mem_avg_mb":     round(sum(mems)/len(mems), 2) if mems else 0,
        "samples":        data["samples"][-50:],
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(snapshot, f, indent=2)
    last_save = time.time()
    print(f"\n💾 Resultado salvo: {RESULTS_PATH}")
    print(f"   Conexões:{snapshot['connections']} | "
          f"TX:{snapshot['bytes_tx']}B | RX:{snapshot['bytes_rx']}B | "
          f"Lat:{snapshot['latency_avg_ms']}ms | "
          f"CPU:{snapshot['cpu_avg_pct']}% | Mem:{snapshot['mem_avg_mb']}MB\n")

def handle_event(cpu, raw, size):
    global last_save
    e    = ct.cast(raw, ct.POINTER(Event)).contents
    proc = e.comm.decode("utf-8", errors="replace").strip("\x00")
    now  = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    pid  = e.pid

    cpu_pct  = 0.0
    wall_now = time.time_ns()
    if pid in _prev_cpu_ns:
        dcpu  = e.cpu_time_ns - _prev_cpu_ns[pid]
        dwall = wall_now      - _prev_wall_ns[pid]
        cpu_pct = round((dcpu / dwall) * 100, 2) if dwall > 0 else 0.0
    _prev_cpu_ns[pid]  = e.cpu_time_ns
    _prev_wall_ns[pid] = wall_now

    mem_mb = round(e.vm_rss_kb / 1024, 2)

    if e.event_type == 1:
        data["connections"] += 1
        label = "CONNECT"
    elif e.event_type == 2:
        data["bytes_tx"] += e.bytes_count
        label = "SEND"
    else:
        data["bytes_rx"] += e.bytes_count
        if e.latency_ns > 0:
            data["latencies_ms"].append(round(e.latency_ns / 1e6, 4))
        label = "RECV"

    if cpu_pct > 0: data["cpu_pct"].append(cpu_pct)
    if mem_mb  > 0: data["mem_mb"].append(mem_mb)

    data["samples"].append({
        "time":       now,
        "event":      label,
        "pid":        pid,
        "proc":       proc,
        "latency_ms": round(e.latency_ns / 1e6, 4) if e.latency_ns > 0 else 0,
        "cpu_pct":    cpu_pct,
        "mem_mb":     mem_mb,
        "bytes":      e.bytes_count,
    })

    lat_str = f"lat={round(e.latency_ns/1e6,2)}ms " if e.latency_ns > 0 else ""
    print(f"[{now}] {label:<8} PID:{pid:<6} {proc:<14} {lat_str}cpu={cpu_pct}% mem={mem_mb}MB")

    if time.time() - last_save >= SAVE_INTERVAL:
        save_results()

def main():
    print("=" * 60)
    print("  🔍 Coletor eBPF — porta 9999")
    print("  Métricas: CPU · Memória · Latência · Bytes · Conexões")
    print("=" * 60)
    b = BPF(text=bpf_program)
    b.attach_kprobe(event="tcp_v4_connect",     fn_name="trace_connect")
    b.attach_kprobe(event="__x64_sys_sendto",   fn_name="trace_send")
    b.attach_kprobe(event="__x64_sys_recvfrom", fn_name="trace_recv")
    print("✅ Probes: tcp_v4_connect | sys_sendto | sys_recvfrom\n")
    b["events"].open_perf_buffer(handle_event)
    try:
        while True:
            b.perf_buffer_poll(timeout=100)
    except KeyboardInterrupt:
        print("\n[!] Encerrando coletor eBPF...")
        save_results()

if __name__ == "__main__":
    main()
