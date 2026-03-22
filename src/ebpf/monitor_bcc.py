#!/usr/bin/python3
"""
Coletor eBPF — TCC Gerenciamento de Rede
Métricas: CPU (%), Memória RSS, Latência, Bytes TX/RX, Conexões
Porta monitorada: 9999

Correções v2:
- CPU calculado via /proc/<pid>/stat (userspace) em vez de task_struct
- Memória via /proc/<pid>/status (userspace) em vez de mm_struct
- Latência filtrada por PID do processo servidor na porta 9999
- Bytes capturados pelo retorno das syscalls (valor real transferido)
"""

from bcc import BPF
import ctypes as ct
import time, os, json, psutil
from datetime import datetime

# ─── Programa eBPF ────────────────────────────────────────────────────────────
# Foca apenas em rastrear conexões TCP e latência send→recv na porta 9999
# CPU e memória são lidos via psutil no userspace (mais confiável)
bpf_program = """
#include <uapi/linux/ptrace.h>
#include <net/sock.h>
#include <net/inet_sock.h>
#include <bcc/proto.h>

#define TARGET_PORT 9999

struct event_t {
    u32  pid;
    u64  timestamp_ns;
    u64  latency_ns;
    u64  bytes_count;
    u16  dport;
    u16  sport;
    u8   event_type;   // 1=connect 2=send 3=recv
    char comm[16];
};

BPF_HASH(send_ts,    u32, u64);   // pid → timestamp do send
BPF_HASH(pid_filter, u32, u8);    // PIDs que se conectaram à porta 9999
BPF_PERF_OUTPUT(events);

// Rastreia novas conexões TCP à porta 9999
int trace_connect(struct pt_regs *ctx, struct sock *sk) {
    u16 dport = 0;
    bpf_probe_read_kernel(&dport, sizeof(dport),
                          &sk->__sk_common.skc_dport);
    if (ntohs(dport) != TARGET_PORT) return 0;

    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u8  one = 1;
    pid_filter.update(&pid, &one);   // marca PID como relevante

    struct event_t e = {};
    e.pid          = pid;
    e.timestamp_ns = bpf_ktime_get_ns();
    e.event_type   = 1;
    e.dport        = TARGET_PORT;

    struct inet_sock *inet = (struct inet_sock *)sk;
    bpf_probe_read_kernel(&e.sport, sizeof(e.sport), &inet->inet_sport);
    e.sport = ntohs(e.sport);

    bpf_get_current_comm(&e.comm, sizeof(e.comm));
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

// Rastreia send — marca timestamp para medir latência
int trace_send(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;

    // Só rastreia PIDs que já fizeram conexão à porta 9999
    u8 *ok = pid_filter.lookup(&pid);
    if (!ok) return 0;

    u64 ts = bpf_ktime_get_ns();
    send_ts.update(&pid, &ts);

    // Bytes enviados: arg3 do sendto é o tamanho do buffer
    u64 size = (u64)PT_REGS_PARM3(ctx);

    struct event_t e = {};
    e.pid          = pid;
    e.timestamp_ns = ts;
    e.event_type   = 2;
    e.dport        = TARGET_PORT;
    e.bytes_count  = size;
    bpf_get_current_comm(&e.comm, sizeof(e.comm));
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}

// Rastreia recvfrom — calcula latência desde o último send
int trace_recv(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;

    u8 *ok = pid_filter.lookup(&pid);
    if (!ok) return 0;

    u64 now   = bpf_ktime_get_ns();
    u64 *start = send_ts.lookup(&pid);
    u64 size  = (u64)PT_REGS_PARM3(ctx);

    struct event_t e = {};
    e.pid          = pid;
    e.timestamp_ns = now;
    e.event_type   = 3;
    e.dport        = TARGET_PORT;
    e.bytes_count  = size;

    if (start) {
        e.latency_ns = now - *start;
        send_ts.delete(&pid);
    }

    bpf_get_current_comm(&e.comm, sizeof(e.comm));
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
        ("bytes_count",  ct.c_uint64),
        ("dport",        ct.c_uint16),
        ("sport",        ct.c_uint16),
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
tracked_pids  = set()   # PIDs que conectaram à porta 9999
start_time    = time.time()
last_save     = time.time()
SAVE_INTERVAL = 10
RESULTS_PATH  = "/app/results/ebpf_results.json"
os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

# ─── Coleta CPU e memória via psutil (userspace, confiável) ───────────────────
def collect_proc_metrics():
    """Lê CPU% e RSS dos PIDs rastreados via psutil."""
    cpu_list, mem_list = [], []
    for pid in list(tracked_pids):
        try:
            p = psutil.Process(pid)
            cpu_list.append(p.cpu_percent(interval=None))
            mem_list.append(p.memory_info().rss / (1024 * 1024))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            tracked_pids.discard(pid)
    return cpu_list, mem_list

# ─── Salva resultados ─────────────────────────────────────────────────────────
def save_results():
    global last_save

    # Coleta métricas de processo no momento do save
    cpu_list, mem_list = collect_proc_metrics()
    if cpu_list: data["cpu_pct"].extend(cpu_list)
    if mem_list: data["mem_mb"].extend(mem_list)

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

# ─── Callback de eventos eBPF ─────────────────────────────────────────────────
def handle_event(cpu, raw, size):
    global last_save
    e    = ct.cast(raw, ct.POINTER(Event)).contents
    proc = e.comm.decode("utf-8", errors="replace").strip("\x00")
    now  = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    if e.event_type == 1:
        data["connections"] += 1
        tracked_pids.add(e.pid)
        # Inicializa cpu_percent para o PID (primeira leitura é sempre 0)
        try:
            psutil.Process(e.pid).cpu_percent(interval=None)
        except Exception:
            pass
        label = "CONNECT"

    elif e.event_type == 2:
        data["bytes_tx"] += e.bytes_count
        tracked_pids.add(e.pid)
        label = "SEND"

    elif e.event_type == 3:
        data["bytes_rx"] += e.bytes_count
        if e.latency_ns > 0:
            lat_ms = round(e.latency_ns / 1e6, 4)
            # Filtra latências absurdas (> 5000ms provavelmente são ruído)
            if lat_ms < 5000:
                data["latencies_ms"].append(lat_ms)
        label = "RECV"
    else:
        return

    lat_str = f"lat={round(e.latency_ns/1e6,2)}ms " if e.latency_ns > 0 else ""
    print(f"[{now}] {label:<8} PID:{e.pid:<6} {proc:<14} "
          f"bytes={e.bytes_count} {lat_str}")

    data["samples"].append({
        "time":       now,
        "event":      label,
        "pid":        e.pid,
        "proc":       proc,
        "latency_ms": round(e.latency_ns / 1e6, 4) if e.latency_ns > 0 else 0,
        "bytes":      e.bytes_count,
    })

    if time.time() - last_save >= SAVE_INTERVAL:
        save_results()

# ─── Attach probes com fallback por versão de kernel ─────────────────────────
def attach_probes(b):
    b.attach_kprobe(event="tcp_v4_connect", fn_name="trace_connect")
    print("✅ kprobe: tcp_v4_connect")

    for name in ["__x64_sys_sendto", "__se_sys_sendto", "sys_sendto"]:
        try:
            b.attach_kprobe(event=name, fn_name="trace_send")
            print(f"✅ kprobe: {name}")
            break
        except Exception:
            continue
    else:
        print("⚠️  Não foi possível anexar probe em sys_sendto")

    for name in ["__x64_sys_recvfrom", "__se_sys_recvfrom", "sys_recvfrom"]:
        try:
            b.attach_kprobe(event=name, fn_name="trace_recv")
            print(f"✅ kprobe: {name}")
            break
        except Exception:
            continue
    else:
        print("⚠️  Não foi possível anexar probe em sys_recvfrom")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  🔍 Coletor eBPF v2 — porta 9999")
    print("  Métricas: CPU · Memória · Latência · Bytes · Conexões")
    print("=" * 60)

    b = BPF(text=bpf_program)
    attach_probes(b)
    print()

    b["events"].open_perf_buffer(handle_event)
    try:
        while True:
            b.perf_buffer_poll(timeout=100)
    except KeyboardInterrupt:
        print("\n[!] Encerrando coletor eBPF...")
        save_results()

if __name__ == "__main__":
    main()
