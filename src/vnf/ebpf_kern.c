/*
 * ebpf_kern.c — Programa BPF CO-RE para kprobes TCP WAF (sport=8080)
 *
 * Compilado em tempo de execução do container via entrypoint:
 *   bpftool btf dump file /sys/kernel/btf/vmlinux format c > /tmp/vmlinux.h
 *   clang -g -O2 -target bpf -D__TARGET_ARCH_x86_64 -I/tmp -I/usr/include/bpf \
 *         -c ebpf_kern.c -o /tmp/ebpf_kern.o
 *
 * Carregado em runtime pelo observador_ebpf_libbpf.py via ctypes + libbpf.
 * Não requer BCC nem LLVM no processo Python.
 */

#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

/* Mapa: índice 0 = bytes RX, índice 1 = bytes TX */
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 2);
    __type(key, __u32);
    __type(value, __u64);
} net_stats SEC(".maps");

/* WAF TX: resposta do WAF ao cliente (socket servidor, sport=8080) */
SEC("kprobe/tcp_sendmsg")
int BPF_KPROBE(kprobe_tcp_sendmsg, struct sock *sk, struct msghdr *msg, size_t size)
{
    __u16 sport = BPF_CORE_READ(sk, __sk_common.skc_num);
    if (sport != 8080)
        return 0;
    __u32 key = 1;
    __u64 *val = bpf_map_lookup_elem(&net_stats, &key);
    if (val)
        __sync_fetch_and_add(val, size);
    return 0;
}

/* WAF RX: requisição do cliente chegando ao WAF (sport=8080) */
SEC("kprobe/tcp_cleanup_rbuf")
int BPF_KPROBE(kprobe_tcp_cleanup_rbuf, struct sock *sk, int copied)
{
    if (copied <= 0)
        return 0;
    __u16 sport = BPF_CORE_READ(sk, __sk_common.skc_num);
    if (sport != 8080)
        return 0;
    __u32 key = 0;
    __u64 *val = bpf_map_lookup_elem(&net_stats, &key);
    if (val)
        __sync_fetch_and_add(val, (__u64)copied);
    return 0;
}

char LICENSE[] SEC("license") = "GPL";
