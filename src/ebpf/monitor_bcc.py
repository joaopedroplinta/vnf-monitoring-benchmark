#!/usr/bin/python3
"""
Coletor eBPF v7 — TCC Gerenciamento de Rede
- Conexões: tracepoint inet_sock_set_state (porta 9999)
- Bytes/Latência: tracepoint sys_enter_sendto/recvfrom
  PIDs do servidor detectados via psutil e injetados no mapa
Porta monitorada: 9999
"""

from bcc import BPF
import ctypes as ct
import time, os, json, psutil
from datetime import datetime

TARGET_PORT = 9999

bpf_program = """
#include <linux/tcp.h>

#define TARGET_PORT 9999

BPF_HASH(conn_count,   u32, u64);
BPF_HASH(bytes_tx_map, u32, u64);
BPF_HASH(bytes_rx_map, u32, u64);
BPF_HASH(send_ts,      u32, u64);
BPF_HASH(latency_map,  u32, u64);
BPF_HASH(pid_filter,   u32, u8);

// Conexões TCP saindo para porta 9999
TRACEPOINT_PROBE(sock, inet_sock_set_state) {
    if (args->protocol != IPPROTO_TCP) return 0;
    if (args->newstate != TCP_SYN_SENT) return 0;
    if (args->dport != TARGET_PORT) return 0;

    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u8  one = 1;
    pid_filter.update(&pid, &one);

    u32 key = 0; u64 zero = 0, *cnt;
    cnt = conn_count.lookup_or_try_init(&key, &zero);
    if (cnt) (*cnt)++;
    return 0;
}

// Bytes TX
// TX enter — marca timestamp para latência
TRACEPOINT_PROBE(syscalls, sys_enter_sendto) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u8 *ok  = pid_filter.lookup(&pid);
    if (!ok) return 0;
    u64 ts = bpf_ktime_get_ns();
    send_ts.update(&pid, &ts);
    return 0;
}

// TX exit — captura bytes via sendto filtrando por PID OU TID
TRACEPOINT_PROBE(syscalls, sys_exit_sendto) {
    if (args->ret <= 0) return 0;
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u32 tid = bpf_get_current_pid_tgid() & 0xFFFFFFFF;
    // Aceita se PID ou TID estiver no filtro
    u8 *ok_pid = pid_filter.lookup(&pid);
    u8 *ok_tid = pid_filter.lookup(&tid);
    if (!ok_pid && !ok_tid) return 0;
    u64 size = (u64)args->ret;
    u64 zero = 0, *acc;
    acc = bytes_tx_map.lookup_or_try_init(&pid, &zero);
    if (acc) (*acc) += size;
    return 0;
}

// Bytes RX + latência
TRACEPOINT_PROBE(syscalls, sys_enter_recvfrom) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u8 *ok  = pid_filter.lookup(&pid);
    if (!ok) return 0;

    u64 now  = bpf_ktime_get_ns();
    u64 size = (u64)args->size;
    u64 zero = 0, *acc, *start;

    acc = bytes_rx_map.lookup_or_try_init(&pid, &zero);
    if (acc) (*acc) += size;

    start = send_ts.lookup(&pid);
    if (start && now > *start) {
        u64 lat = now - *start;
        latency_map.update(&pid, &lat);
        send_ts.delete(&pid);
    }
    return 0;
}
"""

SAVE_INTERVAL = 10
POLL_INTERVAL = 1
RESULTS_PATH  = "/app/results/ebpf_results.json"
os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

data = {
    "connections":  0,
    "bytes_tx":     0,
    "bytes_rx":     0,
    "latencies_ms": [],
    "cpu_pct":      [],
    "mem_mb":       [],
    "samples":      [],
}
start_time   = time.time()
last_save    = time.time()
tracked_pids = set()

def inject_server_pids(b):
    """Injeta PID principal e todos TIDs filhos do servidor (porta 9999)."""
    server_pids = set()
    for conn in psutil.net_connections(kind="tcp"):
        if conn.laddr and conn.laddr.port == TARGET_PORT and conn.pid:
            server_pids.add(conn.pid)

    for pid in server_pids:
        try:
            p = psutil.Process(pid)
            b["pid_filter"][ct.c_uint32(pid)] = ct.c_uint8(1)
            tracked_pids.add(pid)
            psutil.Process(pid).cpu_percent(interval=None)
            # Injeta TIDs das threads filhas (cada conexão aceita cria uma thread)
            for t in p.threads():
                b["pid_filter"][ct.c_uint32(t.id)] = ct.c_uint8(1)
                tracked_pids.add(t.id)
            # Injeta também processos filhos (caso use multiprocessing)
            for child in p.children(recursive=True):
                b["pid_filter"][ct.c_uint32(child.pid)] = ct.c_uint8(1)
                tracked_pids.add(child.pid)
                for t in child.threads():
                    b["pid_filter"][ct.c_uint32(t.id)] = ct.c_uint8(1)
                    tracked_pids.add(t.id)
        except Exception:
            pass

def collect_proc_metrics():
    cpu_list, mem_list = [], []
    for pid in list(tracked_pids):
        try:
            p = psutil.Process(pid)
            cpu_list.append(p.cpu_percent(interval=None))
            mem_list.append(p.memory_info().rss / (1024 * 1024))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            tracked_pids.discard(pid)
    return cpu_list, mem_list

def save_results():
    global last_save
    cpu_l, mem_l = collect_proc_metrics()
    if cpu_l: data["cpu_pct"].extend(cpu_l)
    if mem_l: data["mem_mb"].extend(mem_l)

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
    print(f"\n💾 {RESULTS_PATH}")
    print(f"   conns:{snapshot['connections']} | "
          f"TX:{snapshot['bytes_tx']}B | RX:{snapshot['bytes_rx']}B | "
          f"lat:{snapshot['latency_avg_ms']}ms | "
          f"cpu:{snapshot['cpu_avg_pct']}% | mem:{snapshot['mem_avg_mb']}MB\n",
          flush=True)

def poll_maps(b):
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    try:
        cnt = b["conn_count"][ct.c_uint32(0)].value
        if cnt != data["connections"]:
            diff = cnt - data["connections"]
            data["connections"] = cnt
            print(f"[{now}] CONNECT  +{diff} (total={cnt})", flush=True)
    except KeyError:
        pass

    total_tx, total_rx = 0, 0
    for k, v in b["bytes_tx_map"].items():
        total_tx += v.value
        tracked_pids.add(k.value)
        try: psutil.Process(k.value).cpu_percent(interval=None)
        except: pass
    for k, v in b["bytes_rx_map"].items():
        total_rx += v.value
        tracked_pids.add(k.value)

    if total_tx != data["bytes_tx"] or total_rx != data["bytes_rx"]:
        data["bytes_tx"] = total_tx
        data["bytes_rx"] = total_rx
        print(f"[{now}] BYTES    TX={total_tx}B RX={total_rx}B", flush=True)

    for k, v in b["latency_map"].items():
        lat_ms = round(v.value / 1e6, 4)
        if 0 < lat_ms < 5000:
            data["latencies_ms"].append(lat_ms)
            print(f"[{now}] LATENCY  pid={k.value} lat={lat_ms}ms", flush=True)
    b["latency_map"].clear()

    data["samples"].append({
        "time":        now,
        "bytes_tx":    total_tx,
        "bytes_rx":    total_rx,
        "connections": data["connections"],
    })

def main():
    print("=" * 60)
    print("  🔍 Coletor eBPF v7 — porta 9999 (tracepoints)")
    print("  Métricas: CPU · Memória · Latência · Bytes · Conexões")
    print("=" * 60, flush=True)

    b = BPF(text=bpf_program)
    print("✅ tracepoints: inet_sock_set_state | sys_sendto | sys_recvfrom",
          flush=True)

    counter = 0
    try:
        while True:
            time.sleep(POLL_INTERVAL)
            counter += 1
            # Injeta PIDs do servidor a cada 3s
            if counter % 1 == 0:  # injeta a cada segundo para pegar threads novas
                inject_server_pids(b)
            poll_maps(b)
            if time.time() - last_save >= SAVE_INTERVAL:
                save_results()
    except KeyboardInterrupt:
        print("\n[!] Encerrando coletor eBPF...")
        save_results()

if __name__ == "__main__":
    main()
