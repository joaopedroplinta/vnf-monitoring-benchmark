#!/usr/bin/env python3
"""
Monitor de Sockets com eBPF - TCC
Compatível com kernel 6.6 (WSL2)
Features: TCP + UDP, estatísticas em tempo real, filtros por processo/porta
"""

from bcc import BPF
from socket import inet_ntop, AF_INET
from struct import pack
import ctypes as ct
import datetime
import argparse
import time
import os
from collections import defaultdict

#  Argumentos de linha de comando 
parser = argparse.ArgumentParser(description="Monitor de Sockets eBPF")
parser.add_argument("--proc",  "-p", help="Filtrar por nome de processo (ex: curl)")
parser.add_argument("--port",  "-P", type=int, help="Filtrar por porta destino (ex: 443)")
parser.add_argument("--proto", "-r", choices=["tcp", "udp", "all"], default="all", help="Protocolo a monitorar")
parser.add_argument("--stats", "-s", type=int, default=10, help="Intervalo de estatísticas em segundos (0 = desativa)")
args = parser.parse_args()

#  Programa eBPF 
bpf_program = """
#include <uapi/linux/ptrace.h>
#include <net/sock.h>
#include <net/inet_sock.h>
#include <bcc/proto.h>

struct event_t {
    u32 pid;
    u32 saddr;
    u32 daddr;
    u16 sport;
    u16 dport;
    u8  protocol;
    char comm[16];
};

BPF_PERF_OUTPUT(events);

static inline void fill_event(struct pt_regs *ctx, struct sock *sk,
                               struct event_t *e, u8 proto) {
    u16 family = 0;
    bpf_probe_read_kernel(&family, sizeof(family), &sk->__sk_common.skc_family);
    if (family != AF_INET)
        return;

    e->pid      = bpf_get_current_pid_tgid() >> 32;
    e->protocol = proto;

    bpf_probe_read_kernel(&e->saddr, sizeof(e->saddr), &sk->__sk_common.skc_rcv_saddr);
    bpf_probe_read_kernel(&e->daddr, sizeof(e->daddr), &sk->__sk_common.skc_daddr);

    u16 dport = 0;
    bpf_probe_read_kernel(&dport, sizeof(dport), &sk->__sk_common.skc_dport);
    e->dport = ntohs(dport);

    struct inet_sock *inet = (struct inet_sock *)sk;
    bpf_probe_read_kernel(&e->sport, sizeof(e->sport), &inet->inet_sport);
    e->sport = ntohs(e->sport);

    bpf_get_current_comm(&e->comm, sizeof(e->comm));
    events.perf_submit(ctx, e, sizeof(*e));
}

int trace_tcp_connect(struct pt_regs *ctx, struct sock *sk) {
    struct event_t e = {};
    fill_event(ctx, sk, &e, 6);
    return 0;
}

int trace_udp_sendmsg(struct pt_regs *ctx, struct sock *sk) {
    struct event_t e = {};
    fill_event(ctx, sk, &e, 17);
    return 0;
}
"""

#  Estrutura Python 
class Event(ct.Structure):
    _fields_ = [
        ("pid",      ct.c_uint32),
        ("saddr",    ct.c_uint32),
        ("daddr",    ct.c_uint32),
        ("sport",    ct.c_uint16),
        ("dport",    ct.c_uint16),
        ("protocol", ct.c_uint8),
        ("comm",     ct.c_char * 16),
    ]

#  Estatísticas 
stats = {
    "total": 0,
    "tcp": 0,
    "udp": 0,
    "by_proc": defaultdict(int),
    "by_port": defaultdict(int),
    "by_ip":   defaultdict(int),
}
start_time = time.time()
last_stats  = time.time()

def print_stats():
    elapsed = int(time.time() - start_time)
    print("\n" + "=" * 70)
    print(f"  📊 ESTATÍSTICAS — {elapsed}s de monitoramento")
    print("=" * 70)
    print(f"  Total de eventos : {stats['total']}")
    print(f"  TCP              : {stats['tcp']}")
    print(f"  UDP              : {stats['udp']}")

    if stats["by_proc"]:
        print("\n  Top processos:")
        for proc, cnt in sorted(stats["by_proc"].items(), key=lambda x: -x[1])[:5]:
            print(f"    {proc:<20} {cnt} eventos")

    if stats["by_port"]:
        print("\n  Top portas destino:")
        for port, cnt in sorted(stats["by_port"].items(), key=lambda x: -x[1])[:5]:
            print(f"    :{port:<8} {cnt} eventos")

    if stats["by_ip"]:
        print("\n  Top IPs destino:")
        for ip, cnt in sorted(stats["by_ip"].items(), key=lambda x: -x[1])[:5]:
            print(f"    {ip:<20} {cnt} eventos")
    print("=" * 70 + "\n")

#  Callback 
def handle_event(cpu, data, size):
    global last_stats
    event = ct.cast(data, ct.POINTER(Event)).contents

    if event.daddr == 0:
        return

    proto = "TCP" if event.protocol == 6 else "UDP"
    proc  = event.comm.decode("utf-8", errors="replace").strip('\x00')
    dst   = inet_ntop(AF_INET, pack("I", event.daddr))
    src   = inet_ntop(AF_INET, pack("I", event.saddr))

    #  Filtros 
    if args.proto == "tcp" and event.protocol != 6:
        return
    if args.proto == "udp" and event.protocol != 17:
        return
    if args.proc and args.proc.lower() not in proc.lower():
        return
    if args.port and event.dport != args.port:
        return

    #  Atualiza stats 
    stats["total"] += 1
    stats["tcp" if event.protocol == 6 else "udp"] += 1
    stats["by_proc"][proc] += 1
    stats["by_port"][event.dport] += 1
    stats["by_ip"][dst] += 1

    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {proto:3s} | PID: {event.pid:<6} | PROC: {proc:<16} | "
          f"{src}:{event.sport} → {dst}:{event.dport}")

    #  Exibe stats periodicamente 
    if args.stats > 0 and (time.time() - last_stats) >= args.stats:
        print_stats()
        last_stats = time.time()

#  Main 
def main():
    print("=" * 70)
    print("  Monitor de Sockets eBPF - TCC")
    filtros = []
    if args.proc:  filtros.append(f"processo={args.proc}")
    if args.port:  filtros.append(f"porta={args.port}")
    if args.proto != "all": filtros.append(f"protocolo={args.proto.upper()}")
    if filtros:
        print(f"  Filtros ativos: {', '.join(filtros)}")
    if args.stats > 0:
        print(f"  Estatísticas a cada {args.stats}s")
    print("  Ctrl+C para sair")
    print("=" * 70)
    print(f"{'HORA':<10} {'PROTO':<5} {'PID':<10} {'PROCESSO':<18} {'CONEXÃO'}")
    print("-" * 70)

    b = BPF(text=bpf_program)
    b.attach_kprobe(event="tcp_v4_connect", fn_name="trace_tcp_connect")
    b.attach_kprobe(event="udp_sendmsg",    fn_name="trace_udp_sendmsg")
    b["events"].open_perf_buffer(handle_event)

    try:
        while True:
            b.perf_buffer_poll()
    except KeyboardInterrupt:
        print("\n[!] Monitoramento encerrado.")
        print_stats()

if __name__ == "__main__":
    main()