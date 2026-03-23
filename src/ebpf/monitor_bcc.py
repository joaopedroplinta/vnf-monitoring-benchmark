#!/usr/bin/python3
"""
Coletor eBPF v13-final — TCC Gerenciamento de Rede

Correções aplicadas:
  - RX: usa sys_exit_recvfrom (args->ret = bytes reais recebidos)
        em vez de sys_enter_recvfrom (args->size = tamanho do buffer)
  - TX: sys_exit_write filtrado por TGID do servidor (via psutil) ✅
  - Latência: delta entre sys_enter_sendto/sendmsg e sys_exit_recvfrom
  - Conexões: conta TCP_SYN_SENT (total de conexões iniciadas pelo cliente)

Porta monitorada: 9999 | Duração: 15 minutos
"""

from bcc import BPF
import ctypes as ct
import time, os, json, psutil
from datetime import datetime

TARGET_PORT = 9999
DURATION    = 900  # 15 minutos

bpf_program = """
#include <linux/tcp.h>

#define TARGET_PORT 9999

BPF_HASH(conn_count,   u32, u64);  // key=0 → total conexões iniciadas
BPF_HASH(tx_bytes,     u32, u64);  // key=0 → total bytes TX (servidor)
BPF_HASH(rx_bytes,     u32, u64);  // key=0 → total bytes RX reais (cliente)
BPF_HASH(cli_send_ts,  u32, u64);  // pid   → timestamp send cliente
BPF_HASH(latency_map,  u32, u64);  // pid   → última latência (ns)
BPF_HASH(cli_filter,   u32, u8);   // PIDs do cliente (SYN_SENT → porta 9999)
BPF_HASH(srv_tgid_map, u32, u8);   // TGIDs do servidor (injetado via Python)

// ── Detecta cliente: TCP_SYN_SENT → porta 9999 ──────────────────────────────
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

// ── TX do servidor: sys_exit_write filtrado por TGID ─────────────────────────
TRACEPOINT_PROBE(syscalls, sys_exit_write) {
    if (args->ret <= 0) return 0;
    u32 tgid = bpf_get_current_pid_tgid() >> 32;
    u8 *ok = srv_tgid_map.lookup(&tgid);
    if (!ok) return 0;
    u32 key = 0; u64 zero = 0, *acc;
    acc = tx_bytes.lookup_or_try_init(&key, &zero);
    if (acc) (*acc) += (u64)args->ret;
    return 0;
}

// ── Latência: timestamp quando cliente envia ─────────────────────────────────
TRACEPOINT_PROBE(syscalls, sys_enter_sendto) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u8 *ok = cli_filter.lookup(&pid);
    if (!ok) return 0;
    u64 ts = bpf_ktime_get_ns();
    cli_send_ts.update(&pid, &ts);
    return 0;
}

TRACEPOINT_PROBE(syscalls, sys_enter_sendmsg) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u8 *ok = cli_filter.lookup(&pid);
    if (!ok) return 0;
    u64 ts = bpf_ktime_get_ns();
    cli_send_ts.update(&pid, &ts);
    return 0;
}

// ── RX do cliente: bytes REAIS recebidos (ret do recvfrom) + latência ─────────
TRACEPOINT_PROBE(syscalls, sys_exit_recvfrom) {
    if (args->ret <= 0) return 0;   // ignora erros e conexões fechadas
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u8 *ok = cli_filter.lookup(&pid);
    if (!ok) return 0;

    u64 now  = bpf_ktime_get_ns();
    u64 zero = 0, *acc, *start;

    // RX: bytes reais retornados pela syscall
    u32 key = 0;
    acc = rx_bytes.lookup_or_try_init(&key, &zero);
    if (acc) (*acc) += (u64)args->ret;

    // Latência: delta desde o send do cliente
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
tracked_pids = set()

def find_server_tgids():
    """Encontra TGIDs do servidor via psutil — processo com LISTEN na porta 9999."""
    tgids = set()
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if (conn.laddr and conn.laddr.port == TARGET_PORT
                    and conn.status == "LISTEN" and conn.pid):
                tgids.add(conn.pid)
                tracked_pids.add(conn.pid)
                try:
                    p = psutil.Process(conn.pid)
                    for child in p.children(recursive=True):
                        tgids.add(child.pid)
                        tracked_pids.add(child.pid)
                except Exception:
                    pass
    except Exception:
        pass
    return tgids

def inject_server_tgids(b, tgids):
    """Injeta TGIDs do servidor no mapa BPF srv_tgid_map."""
    one = ct.c_uint8(1)
    for tgid in tgids:
        b["srv_tgid_map"][ct.c_uint32(tgid)] = one
    print(f"✅ TGIDs do servidor injetados: {tgids}", flush=True)

def update_tracked_pids():
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr and conn.laddr.port == TARGET_PORT and conn.pid:
                tracked_pids.add(conn.pid)
                try:
                    p = psutil.Process(conn.pid)
                    for child in p.children(recursive=True):
                        tracked_pids.add(child.pid)
                except Exception:
                    pass
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
    elapsed = round(time.time() - start_time, 0)
    print(f"\n💾 [{elapsed}s/{DURATION}s]")
    print(f"   conns:{snapshot['connections']} | "
          f"TX:{snapshot['bytes_tx']}B | RX:{snapshot['bytes_rx']}B | "
          f"lat:{snapshot['latency_avg_ms']}ms | "
          f"cpu:{snapshot['cpu_avg_pct']}% | mem:{snapshot['mem_avg_mb']}MB",
          flush=True)

def poll_maps(b):
    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

    try:
        cnt = b["conn_count"][ct.c_uint32(0)].value
        if cnt != data["connections"]:
            data["connections"] = cnt
            print(f"[{now}] CONNECT total={cnt} "
                  f"srv_tgids={len(b['srv_tgid_map'])}", flush=True)
    except KeyError:
        pass

    try:
        total_tx = b["tx_bytes"][ct.c_uint32(0)].value
    except KeyError:
        total_tx = data["bytes_tx"]  # mantém último valor conhecido

    try:
        total_rx = b["rx_bytes"][ct.c_uint32(0)].value
    except KeyError:
        total_rx = data["bytes_rx"]

    if total_tx != data["bytes_tx"] or total_rx != data["bytes_rx"]:
        data["bytes_tx"] = total_tx
        data["bytes_rx"] = total_rx
        print(f"[{now}] BYTES TX={total_tx}B RX={total_rx}B "
              f"cli_pids={len(b['cli_filter'])} "
              f"srv_tgids={len(b['srv_tgid_map'])}", flush=True)

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
    print(f"  🔍 Coletor eBPF v13-final — porta {TARGET_PORT}")
    print(f"  TX: sys_exit_write  filtrado por TGID (via psutil)")
    print(f"  RX: sys_exit_recvfrom (bytes reais, não tamanho do buffer)")
    print(f"  Latência: send→recvfrom do cliente")
    print(f"  Duração: {DURATION//60} minutos")
    print("=" * 60, flush=True)

    b = BPF(text=bpf_program)
    print("✅ BPF carregado", flush=True)

    print(f"⏳ Aguardando servidor na porta {TARGET_PORT}...", flush=True)
    server_tgids = set()
    for _ in range(60):
        server_tgids = find_server_tgids()
        if server_tgids:
            break
        time.sleep(1)

    if not server_tgids:
        print(f"⚠️  Servidor não encontrado. TX pode ficar zerado.", flush=True)
    else:
        inject_server_tgids(b, server_tgids)

    for pid in list(tracked_pids):
        try:
            psutil.Process(pid).cpu_percent(interval=None)
        except Exception:
            pass

    try:
        while time.time() - start_time < DURATION:
            time.sleep(POLL_INTERVAL)
            update_tracked_pids()
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