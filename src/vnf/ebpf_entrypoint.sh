#!/bin/bash
# Entrypoint do observador eBPF (libbpf):
#   1. Gera vmlinux.h a partir do BTF do kernel em execução
#   2. Compila ebpf_kern.c → /tmp/ebpf_kern.o com clang
#   3. Inicia observador Python (sem BCC/LLVM no processo)
set -euo pipefail

BPF_SRC="/app/vnf/ebpf_kern.c"
BPF_OBJ="/tmp/ebpf_kern.o"
VMLINUX="/tmp/vmlinux.h"
BTF_FILE="/sys/kernel/btf/vmlinux"

echo "=== [ebpf] Gerando vmlinux.h do kernel $(uname -r) ==="
# Chama o binário diretamente (o wrapper /usr/sbin/bpftool falha em kernels não-Ubuntu)
BPFTOOL=$(find /usr/lib/linux-tools -name bpftool 2>/dev/null | head -1)
if [ -z "$BPFTOOL" ]; then
    echo "[ERRO] bpftool não encontrado em /usr/lib/linux-tools" >&2
    exit 1
fi
"$BPFTOOL" btf dump file "$BTF_FILE" format c > "$VMLINUX"

echo "=== [ebpf] Compilando $BPF_SRC → $BPF_OBJ ==="
clang -g -O2 -target bpf -D__TARGET_ARCH_x86 \
    -I/tmp \
    -I/usr/include/bpf \
    -c "$BPF_SRC" -o "$BPF_OBJ"

echo "=== [ebpf] BPF compilado. Iniciando observador (sem LLVM em memória) ==="
exec python3 /app/vnf/observador_ebpf.py
