#!/usr/bin/python3

from bcc import BPF
import time
import ctypes

# Programa eBPF em C
bpf_text = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

BPF_HASH(connection_count, u16, u64);
BPF_HASH(latency_map, u32, u64);

int trace_accept(struct pt_regs *ctx) {
    u16 port = 9999;
    u64 *count, zero = 0;
    
    count = connection_count.lookup(&port);
    if (count) {
        (*count)++;
    } else {
        connection_count.update(&port, &zero);
    }
    
    bpf_trace_printk("Nova conexão detectada na porta %d\\n", port);
    return 0;
}

int trace_tcp_v4_connect(struct pt_regs *ctx) {
    u16 port = 9999;
    u64 *count, zero = 0;
    
    count = connection_count.lookup(&port);
    if (count) {
        (*count)++;
    } else {
        connection_count.update(&port, &zero);
    }
    bpf_trace_printk("Tentativa de conexão TCP\\n");
    return 0;
}

int trace_sys_enter_sendto(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 ts = bpf_ktime_get_ns();
    latency_map.update(&pid, &ts);
    bpf_trace_printk("Processo %d sendto()\\n", pid);
    return 0;
}

int trace_sys_enter_send(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 ts = bpf_ktime_get_ns();
    latency_map.update(&pid, &ts);
    bpf_trace_printk("Processo %d send()\\n", pid);
    return 0;
}

int trace_sys_exit_recvfrom(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 *start, latency;
    
    start = latency_map.lookup(&pid);
    if (start) {
        latency = bpf_ktime_get_ns() - *start;
        bpf_trace_printk("Processo %d recvfrom latência: %lld ns\\n", pid, latency);
        latency_map.delete(&pid);
    }
    return 0;
}

int trace_sys_exit_recv(struct pt_regs *ctx) {
    u32 pid = bpf_get_current_pid_tgid() >> 32;
    u64 *start, latency;

    start = latency_map.lookup(&pid);
    if (start) {
        latency = bpf_ktime_get_ns() - *start;
        bpf_trace_printk("Processo %d recv() latência: %lld ns\\n", pid, latency);
        latency_map.delete(&pid);
    }
    return 0;
}
"""

# Carrega o programa
print("📊 Inicializando monitor eBPF...")
b = BPF(text=bpf_text)

# Tenta diferentes formas de anexar aos probes
probes_attached = False

functions_to_try = [
    ("kprobe", "sys_accept"),
    ("kprobe", "accept"),
    ("kprobe", "__sys_accept4"),
    ("kprobe", "sys_accept4"),
    ("kprobe", "do_accept"),
    ("kprobe", "inet_accept"),
    ("kretprobe", "sys_accept"),
    ("kretprobe", "accept"),
    ("tracepoint", "syscalls:sys_enter_accept"),
    ("tracepoint", "syscalls:sys_enter_accept4"),
]

for probe_type, func_name in functions_to_try:
    try:
        if probe_type == "kprobe":
            b.attach_kprobe(event=func_name, fn_name="trace_accept")
            print(f"✅ Anexado kprobe em {func_name}")
            probes_attached = True
            break
        elif probe_type == "kretprobe":
            b.attach_kretprobe(event=func_name, fn_name="trace_accept")
            print(f"✅ Anexado kretprobe em {func_name}")
            probes_attached = True
            break
        elif probe_type == "tracepoint":
            b.attach_tracepoint(tp=func_name, fn_name="trace_accept")
            print(f"✅ Anexado tracepoint em {func_name}")
            probes_attached = True
            break
    except Exception:
        continue

if not probes_attached:
    print("⚠️  Não foi possível anexar aos probes padrão, tentando tcp_v4_connect...")
    try:
        b.attach_kprobe(event="tcp_v4_connect", fn_name="trace_tcp_v4_connect")
        print("✅ Anexado kprobe em tcp_v4_connect")
        probes_attached = True
    except Exception:
        pass

if not probes_attached:
    print("❌ Não foi possível anexar nenhum probe. Usando modo de fallback...")
    try:
        b.attach_kprobe(event="sys_sendto", fn_name="trace_sys_enter_sendto")
        b.attach_kprobe(event="sys_send", fn_name="trace_sys_enter_send")
        b.attach_kretprobe(event="sys_recvfrom", fn_name="trace_sys_exit_recvfrom")
        b.attach_kretprobe(event="sys_recv", fn_name="trace_sys_exit_recv")
        print("✅ Anexado probes em sys_send/sys_recv/sys_sendto/sys_recvfrom")
    except Exception as e:
        print(f"❌ Erro no fallback: {e}")
        exit(1)

print("\n📊 Monitorando conexões... Pressione Ctrl+C para sair")
print("-" * 60)

# Função para ler os valores do mapa
def print_stats():
    print("\n📈 ESTATÍSTICAS:")
    print(f"   Conexões na porta 9999: ", end="")
    try:
        count = b["connection_count"][ctypes.c_ushort(9999)].value
        print(f"{count}")
    except KeyError:
        print("0")
    
    # Mostra tamanho do mapa de latência
    latency_size = len(b["latency_map"])
    if latency_size > 0:
        print(f"   Operações em andamento: {latency_size}")

# Loop principal
last_stats_time = time.time()
try:
    while True:
        # Lê os traces do kernel
        try:
            (task, pid, cpu, flags, ts, msg) = b.trace_fields()
            print(f"{ts:.6f} [{pid}] {msg.decode()}")
        except (ValueError, KeyboardInterrupt):
            pass
        except OSError as oe:
            # trace_pipe ocupado por outro leitor; apenas pula
            if oe.errno == 16:
                # outra instância pode estar a usar, tenta novamente
                time.sleep(0.1)
                continue
            else:
                raise
        
        # Mostra estatísticas a cada 5 segundos
        current_time = time.time()
        if current_time - last_stats_time >= 5:
            print_stats()
            last_stats_time = current_time
            
except KeyboardInterrupt:
    print("\n\n👋 Monitor encerrado")
    print_stats()