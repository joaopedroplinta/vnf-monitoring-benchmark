#!/bin/bash

echo "🔧 Compilando programa eBPF..."

# Verifica se o diretório ebpf existe
if [ ! -d "ebpf" ]; then
    echo "❌ Diretório 'ebpf' não encontrado!"
    exit 1
fi

# Verifica se o arquivo monitor.c existe
if [ ! -f "ebpf/monitor.c" ]; then
    echo "❌ Arquivo 'ebpf/monitor.c' não encontrado!"
    exit 1
fi

# Verifica se tem clang
if ! command -v clang &> /dev/null; then
    echo "❌ clang não encontrado. Instalando..."
    sudo apt-get update
    sudo apt-get install -y clang llvm
fi

# Cria diretório para output se não existir
mkdir -p ebpf/output

# Compila o programa eBPF
echo "📝 Compilando ebpf/monitor.c -> ebpf/output/monitor.o"
clang -O2 -target bpf -c ebpf/monitor.c -o ebpf/output/monitor.o

if [ $? -eq 0 ]; then
    echo "✅ Compilação bem sucedida!"
    echo "📋 Arquivo gerado: ebpf/output/monitor.o"
    echo ""
    echo "📋 Para ver informações do programa:"
    echo "   bpftool prog load ebpf/output/monitor.o /sys/fs/bpf/monitor"
    echo "   bpftool prog list | grep -A5 monitor"
else
    echo "❌ Erro na compilação"
    exit 1
fi