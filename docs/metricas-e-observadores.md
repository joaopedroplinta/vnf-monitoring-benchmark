# Métricas coletadas e observadores

## Métricas coletadas

Cada execução gera um JSON em `results/` com estes campos:

| Métrica | Origem | Descrição |
|---------|--------|-----------|
| `observador_latency_avg_ms` | probe | Tempo de resposta médio da roundtrip UDP (métrica principal) |
| `observador_latency_stddev_ms` | probe | Desvio padrão do tempo de resposta |
| `observador_latency_max_ms` | probe | Tempo de resposta máximo observado |
| `observador_samples` | probe | Número de amostras coletadas |
| `bytes_rx / bytes_tx` | observador | eBPF: kprobe `sport=8080`; sysstat/Prometheus: `/proc/net/dev` |
| `cpu_avg_pct` | observador (psutil) | Uso médio de CPU do processo WAF |
| `mem_avg_mb` | observador (psutil) | Uso médio de memória do processo WAF |
| `collector_cpu_avg_pct` | observador (psutil) | Uso médio de CPU do próprio observador |
| `collector_mem_avg_mb` | observador (psutil) | Uso médio de memória do próprio observador |
| `inspect_count` | WAF → observador | Total de mensagens inspecionadas na execução |
| `inspect_avg_ms` | WAF → observador | Tempo médio de inspeção por mensagem (ms) |
| `inspect_min_ms` | WAF → observador | Tempo mínimo de inspeção (ms) |
| `inspect_max_ms` | WAF → observador | Tempo máximo de inspeção (ms) |

## Observadores

### eBPF — `observador_ebpf.py` + `ebpf_kern.c`

- Programa BPF CO-RE compilado com `clang` no entrypoint do contêiner (`ebpf_entrypoint.sh`), a partir do `vmlinux.h` gerado do BTF do kernel em execução.
- Carregado em Python via `ctypes` + `libbpf.so.1`, sem BCC/LLVM no processo.
- `kprobe/tcp_sendmsg`: acumula bytes TX quando `sport == 8080` (respostas do WAF).
- `kprobe/tcp_cleanup_rbuf`: acumula bytes RX quando `sport == 8080` (requisições recebidas pelo WAF).
- Contadores em um mapa `BPF_MAP_TYPE_ARRAY` de duas posições (RX e TX), agregando todas as conexões da porta 8080, sem distinção por conexão individual.
- O filtro `sport=8080` evita dupla contagem no loopback.
- Requer `privileged: true`, `pid: host` e os mounts `/sys/kernel/debug`, `/sys/fs/bpf` e `/sys/kernel/btf`.

### sysstat — `observador_sysstat.py`

- Lê `/proc/net/dev` (interface `lo`) a cada request UDP recebido, sob demanda, sem laço de amostragem próprio.
- Retorna o delta de bytes RX/TX em relação ao início do teste.
- Requer `pid: host`.

### Prometheus — `observador_prometheus.py`

- Mesma lógica de coleta do sysstat.
- Expõe Gauges em `:8000/metrics` via `prometheus_client`. Nenhum servidor Prometheus externo consulta o endpoint durante os testes: o experimento mede só o custo de manter o exporter ativo.
- O bind do UDP `:9999` é feito antes do HTTP `:8000` para evitar falha por TIME_WAIT entre execuções.
- Requer `pid: host`.

Para a visão geral dos componentes, veja [architecture.md](architecture.md).
