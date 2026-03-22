#!/usr/bin/python3
"""
Coletor eBPF v9 — TCC Gerenciamento de Rede
Estratégia: captura TUDO sem filtro no kernel,
filtra no userspace pelos TIDs reais do servidor.
Porta monitorada: 9999 | Duração: 15 minutos
"""

from bcc import BPF
import ctypes as ct
import time, os, json, psutil, sys
from datetime import datetime

TARGET_PORT = 9999
DURATION    = 900  # 15 minutos

# Programa eBPF sem filtro — captura todos os sendto/recvfrom
bpf_program = """
#include <linux/tcp.h>
#define TARGET_PORT 9999

BPF_HASH(conn_count,  u32, u64);
BPF_HASH(tx_by_tid,   u32, u64);  // tid → bytes enviados
BPF_HASH(rx_by_pid,   u32, u64);  // pid → bytes recebidos
BPF_HASH(cli_send_ts, u32, u64);  // pid → timestamp send cliente
BPF_HASH(latency_map, u32, u64);  // pid → latência
BPF_HASH(cli_filter,  u32, u8);   // PIDs do cliente

// Conexões para porta 9999
TRACEPOINT_PROBE(sock, inet_sock_set_state) {
    if (args->protocol != IPPROTO_TCP) return 0;
    if (args->newstate != TCP_SYN_SENT) return 0;
    if (args->dport != TARGET_PORT) return 0;
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u8  one = 1;
    cli_filter.update(&pid, &one);
    u32 key = 0; u64 zero = 0, *cnt;
    cnt = conn_count.lookup_or_try_init(&key, &zero);
    if (cnt) (*cnt)++;
    return 0;
}

// Captura TODOS os sendto sem filtro (filtra no userspace)
TRACEPOINT_PROBE(syscalls, sys_exit_sendto) {
    if (args->ret <= 0) return 0;
    u32 tid  = (u32)(bpf_get_current_pid_tgid() & 0xFFFFFFFF);
    u64 zero = 0, *acc;
    acc = tx_by_tid.lookup_or_try_init(&tid, &zero);
    if (acc) (*acc) += (u64)args->ret;
    return 0;
}

// Marca timestamp do send do cliente
TRACEPOINT_PROBE(syscalls, sys_enter_sendto) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u8 *ok  = cli_filter.lookup(&pid);
    if (!ok) return 0;
    u64 ts = bpf_ktime_get_ns();
    cli_send_ts.update(&pid, &ts);
    return 0;
}

// RX do cliente + latência
TRACEPOINT_PROBE(syscalls, sys_enter_recvfrom) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u8 *ok  = cli_filter.lookup(&pid);
    if (!ok) return 0;
    u64 now  = bpf_ktime_get_ns();
    u64 size = (u64)args->size;
    u64 zero = 0, *acc, *start;
    acc = rx_by_pid.lookup_or_try_init(&pid, &zero);
    if (acc) (*acc) += size;
    start = cli_send_ts.lookup(&pid);
    if (start && now > *start) {
        u64 lat = now - *start;
        latency_map.update(&pid, &lat);
        cli_send_ts.delete(&pid);
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
server_tids  = set()   # TIDs do servidor detectados via psutil
tracked_pids = set()

def update_server_tids():
    """Detecta TIDs do servidor via /proc — funciona cross-namespace."""
    new_tids = set()
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr and conn.laddr.port == TARGET_PORT and conn.pid:
                pid = conn.pid
                tracked_pids.add(pid)
                # Lê TIDs diretamente de /proc/<pid>/task/
                task_dir = f"/proc/{pid}/task"
                if os.path.exists(task_dir):
                    for tid_str in os.listdir(task_dir):
                        try:
                            new_tids.add(int(tid_str))
                        except ValueError:
                            pass
                # Threads filhas via psutil
                try:
                    p = psutil.Process(pid)
                    for t in p.threads():
                        new_tids.add(t.id)
                    for child in p.children(recursive=True):
                        tracked_pids.add(child.pid)
                        for t in child.threads():
                            new_tids.add(t.id)
                except Exception:
                    pass
    except Exception:
        pass
    server_tids.update(new_tids)

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
    elapsed = round(time.time() - start_time, 0)
    print(f"\n💾 [{elapsed}s/{DURATION}s]")
    print(f"   conns:{snapshot['connections']} | "
          f"TX:{snapshot['bytes_tx']}B | RX:{snapshot['bytes_rx']}B | "
          f"lat:{snapshot['latency_avg_ms']}ms | "
          f"cpu:{snapshot['cpu_avg_pct']}% | mem:{snapshot['mem_avg_mb']}MB",
          flush=True)

def poll_maps(b):
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    # Conexões
    try:
        cnt = b["conn_count"][ct.c_uint32(0)].value
        if cnt != data["connections"]:
            data["connections"] = cnt
            print(f"[{now}] CONNECT total={cnt}", flush=True)
    except KeyError:
        pass

    # TX — soma apenas TIDs do servidor
    total_tx = 0
    for k, v in b["tx_by_tid"].items():
        if k.value in server_tids:
            total_tx += v.value

    # RX — soma todos os PIDs do cliente
    total_rx = 0
    for k, v in b["rx_by_pid"].items():
        total_rx += v.value
        tracked_pids.add(k.value)

    if total_tx != data["bytes_tx"] or total_rx != data["bytes_rx"]:
        data["bytes_tx"] = total_tx
        data["bytes_rx"] = total_rx
        print(f"[{now}] BYTES TX={total_tx}B RX={total_rx}B "
              f"(srv_tids={len(server_tids)})", flush=True)

    # Latência
    for k, v in b["latency_map"].items():
        lat_ms = round(v.value / 1e6, 4)
        if 0 < lat_ms < 5000:
            data["latencies_ms"].append(lat_ms)
    b["latency_map"].clear()

    data["samples"].append({
        "time":        now,
        "bytes_tx":    total_tx,
        "bytes_rx":    total_rx,
        "connections": data["connections"],
    })

def main():
    print("=" * 60)
    print(f"  🔍 Coletor eBPF v9 — porta {TARGET_PORT}")
    print(f"  Duração: {DURATION//60} minutos")
    print("=" * 60, flush=True)

    b = BPF(text=bpf_program)
    print("✅ BPF carregado", flush=True)

    # Inicializa cpu_percent
    update_server_tids()
    for pid in list(tracked_pids):
        try: psutil.Process(pid).cpu_percent(interval=None)
        except: pass

    try:
        while time.time() - start_time < DURATION:
            time.sleep(POLL_INTERVAL)
            update_server_tids()
            poll_maps(b)
            if time.time() - last_save >= SAVE_INTERVAL:
                save_results()
    except KeyboardInterrupt:
        print("\n[!] Interrompido")
    finally:
        print("\n[✓] Salvando resultado final...")
        save_results()
        print("[✓] Encerrado.", flush=True)

if __name__ == "__main__":
    main()
