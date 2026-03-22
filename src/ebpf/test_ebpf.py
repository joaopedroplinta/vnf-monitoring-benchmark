from bcc import BPF
import ctypes as ct
import time

bpf_program = """
#include <uapi/linux/ptrace.h>
#include <net/sock.h>
#include <linux/tcp.h>

#define TARGET_PORT 9999

BPF_HASH(conn_count, u32, u64);
BPF_HASH(pid_filter, u32, u8);

TRACEPOINT_PROBE(sock, inet_sock_set_state) {
    if (args->protocol != IPPROTO_TCP) return 0;
    if (args->newstate != TCP_SYN_SENT) return 0;
    if (args->dport != TARGET_PORT) return 0;

    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u8 one = 1;
    pid_filter.update(&pid, &one);

    u32 key = 0;
    u64 zero = 0, *cnt;
    cnt = conn_count.lookup_or_try_init(&key, &zero);
    if (cnt) (*cnt)++;
    return 0;
}
"""

b = BPF(text=bpf_program)
print("✅ Tracepoint sock/inet_sock_set_state carregado")
print("Aguardando 20s...")
time.sleep(20)

try:
    cnt = b["conn_count"][ct.c_uint32(0)].value
    print(f"Conexões na porta 9999: {cnt}")
except KeyError:
    print("Nenhuma conexão detectada")

print("PIDs filtrados:")
for k, v in b["pid_filter"].items():
    print(f"  PID {k.value}")
