# vnf-monitoring-benchmark — eBPF vs Sysstat vs Prometheus

Análise comparativa de desempenho entre três abordagens de monitoramento de rede aplicadas a uma VNF (Virtual Network Function):

1. **eBPF (libbpf+CO-RE)**: coleta no nível do kernel via kprobes (`tcp_sendmsg`, `tcp_cleanup_rbuf`), programa BPF pré-compilado com clang e carregado via `libbpf.so.1` (sem BCC/LLVM em runtime).
2. **sysstat**: polling em userspace via `/proc/net/dev`.
3. **Prometheus**: igual ao sysstat, com exposição adicional de métricas via HTTP (`:8000/metrics`).

O foco é medir o **overhead do monitoramento** (tempo de resposta do observador) ao monitorar um WAF simplificado rodando em Python.

---

## Arquitetura

![Diagrama C4 — Container Diagram (Nível 2)](docs/arquitetura_c4.svg)

- O **WAF** inspeciona cada payload (SQLi, XSS, PathTraversal, RCE, NullByte) via `asyncio` + `ThreadPoolExecutor`, registra o tempo de inspeção e responde ao cliente. Protocolo: framing com 4 bytes de comprimento por mensagem (conexões persistentes).
- O **Observador** coleta métricas do WAF usando a ferramenta correspondente (eBPF / sysstat / Prometheus) e responde a qualquer request UDP com um JSON de métricas.
- O **Probe** envia requests UDP a cada 1s e mede o tempo de resposta (RTT UDP) — essa é a métrica principal de comparação.
- A ferramenta muda entre os testes; o probe é o mesmo script (`probe.py`) nos três casos.

---

## Estrutura do Projeto

```
vnf-monitoring-benchmark/
├── src/
│   ├── probe.py                   # Probe UDP único (configurado por variáveis de ambiente)
│   ├── vnf/
│   │   ├── waf.py                 # WAF TCP (porta 8080) — SQLi, XSS, PathTraversal, RCE, NullByte
│   │   ├── observador_ebpf.py     # Observador eBPF (libbpf+CO-RE): kprobes sport=8080, ~15 MB RSS
│   │   ├── ebpf_kern.c            # Programa BPF CO-RE (kprobes tcp_sendmsg/tcp_cleanup_rbuf)
│   │   ├── ebpf_entrypoint.sh     # Gera vmlinux.h, compila com clang, exec Python
│   │   ├── observador_sysstat.py  # Observador sysstat: /proc/net/dev + psutil WAF
│   │   └── observador_prometheus.py # Observador Prometheus: /proc/net/dev + psutil WAF + HTTP :8000
│   ├── client/
│   │   └── client.py              # Envia payloads pré-gerados ao WAF (asyncio, conexões persistentes)
│   └── compare.py                 # Consolida resultados em CSV e JSON (3 modos)
├── configs/
│   ├── Dockerfile                 # Imagem base Ubuntu 24.04 + Python 3
│   ├── Dockerfile.ebpf-libbpf     # Imagem eBPF: libbpf1 + clang (usada pelo stack ebpf)
│   └── Dockerfile.client          # Imagem para o cliente de tráfego
├── data/
│   └── payloads/                  # Arquivos binários de payloads pré-gerados
│       ├── payloads_100000_6040.bin
│       ├── payloads_500000_6040.bin
│       ├── payloads_1000000_6040.bin
│       └── payloads_2000000_6040.bin
├── scripts/
│   ├── gen_payloads.py            # Gera arquivos de payloads (executar antes dos testes)
│   ├── plot_results.py            # Gera gráficos em results/plots/
│   ├── run_ebpf.sh                # Executa o teste completo com eBPF (libbpf)
│   ├── run_sysstat.sh             # Executa o teste completo com sysstat
│   ├── run_prometheus.sh          # Executa o teste completo com Prometheus
│   └── run_multi.sh               # Executa N repetições sequenciais de uma ferramenta (ebpf|sysstat|prometheus)
├── docs/
│   ├── architecture.md            # Documentação de arquitetura
│   ├── arquitetura_c4.svg         # Diagrama C4 da arquitetura
│   ├── main.tex                   # Documento LaTeX do TCC
│   ├── ifpr-pinhais.cls           # Classe LaTeX IFPR Pinhais
│   └── referencias.bib            # Referências bibliográficas
├── results/                       # Resultados (*_<N>_run<ID>_results.json, .csv, .json)
│   ├── plots/                     # Gráficos gerados por plot_results.py
│   └── pre_testes/                # Runs preliminares de validação
├── docker-compose.ebpf.yml        # Stack eBPF (libbpf+CO-RE)
├── docker-compose.sysstat.yml
└── docker-compose.prometheus.yml
```

---

## Como Rodar

### Ambiente

**Máquina usada nos resultados oficiais:**

| Item | Especificação |
|------|---------------|
| **CPU** | AMD Ryzen 5 5500 (6 núcleos / 12 threads, até 4,27 GHz, L3 16 MB) |
| **RAM** | 16 GB |
| **SO** | Ubuntu 26.04 LTS (Resolute Raccoon) |
| **Kernel** | 7.0.0-15-generic |

**Requisitos mínimos para reproduzir:**
- Linux nativo (kernel 6.10+, testado no 7.0)
- Docker + Docker Compose
- Python 3.10+
- BTF habilitado no kernel (`/sys/kernel/btf/vmlinux` — presente em kernels 5.8+)

**Bibliotecas Python do host** (os contêineres instalam as suas próprias automaticamente via Dockerfile):

```bash
pip install matplotlib numpy          # geração de gráficos (plot_results.py)
```

> `psutil` e `prometheus_client` são instalados apenas dentro dos contêineres — não é necessário instalá-los no host.

### Passo 1 — Gerar os payloads (uma vez)

Os payloads são pré-gerados no host e montados no container do cliente:

```bash
python3 scripts/gen_payloads.py 100000   # → data/payloads/payloads_100000_6040.bin
python3 scripts/gen_payloads.py 500000   # → data/payloads/payloads_500000_6040.bin
python3 scripts/gen_payloads.py 1000000  # → data/payloads/payloads_1000000_6040.bin
```

Opções do gerador:

```bash
python3 scripts/gen_payloads.py <count> [--ratio 60] [--seed 42] [--out FILE]
# --ratio: percentual de mensagens limpas (padrão: 60 → 60% limpos / 40% maliciosos)
# --seed:  semente aleatória para reprodutibilidade (padrão: 42)
```

### Passo 2 — Executar os testes

Cada script sobe a stack completa (WAF + observador + cliente + probe), aguarda o probe finalizar via `docker wait` e exibe um resumo:

```bash
NUM_MESSAGES=100000 bash scripts/run_ebpf.sh
NUM_MESSAGES=100000 bash scripts/run_sysstat.sh
NUM_MESSAGES=100000 bash scripts/run_prometheus.sh
```

O script deriva automaticamente o arquivo de payloads a partir de `NUM_MESSAGES`. Se o arquivo não existir, o script aborta com a instrução de geração.

Variáveis de ambiente:

| Variável | Padrão | Descrição |
|---|---|---|
| `NUM_MESSAGES` | 100000 | Quantidade de mensagens — usada para DURATION e nomenclatura dos resultados |
| `DURATION` | `NUM_MESSAGES/15000 + 20` | Duração da coleta (segundos) |
| `RUN_ID` | 1 | Identificador do run |
| `WORKERS` | 200 | Conexões assíncronas do cliente (coroutines asyncio) |
| `PAYLOADS_FILE_HOST` | `data/payloads/payloads_<N>_6040.bin` | Caminho do arquivo de payloads no host (sobrescreve o padrão) |

### Passo 3 — Múltiplas repetições

```bash
bash scripts/run_multi.sh <ferramenta> <num_messages> <num_runs> [--pre]

# Exemplos:
bash scripts/run_multi.sh ebpf       100000 5
bash scripts/run_multi.sh sysstat    100000 5
bash scripts/run_multi.sh prometheus 100000 5

# Com flag --pre: salva em results/pre_testes/ (testes preliminares)
bash scripts/run_multi.sh prometheus 100000 5 --pre
```

Salva cada repetição como `<ferramenta>_<N>_run<ID>_results.json` e gera a agregação ao final.

### Gerar comparativo

```bash
python3 src/compare.py 100000        # compara 3 ferramentas para N=100000 (run 1)
python3 src/compare.py 100000 5      # agrega 5 runs de N=100000 (média ± desvio)
python3 src/compare.py               # cross-N com todos os valores disponíveis
```

---

## Métricas Coletadas

| Métrica | Origem | Descrição |
|---------|--------|-----------|
| `observador_latency_avg_ms` | probe | Tempo de resposta médio da roundtrip UDP (overhead do monitoramento) |
| `observador_latency_stddev_ms` | probe | Desvio padrão do tempo de resposta |
| `observador_latency_max_ms` | probe | Tempo de resposta máximo observado |
| `observador_samples` | probe | Número de amostras coletadas |
| `bytes_rx / bytes_tx` | observador | eBPF: kprobe sport=8080; sysstat/Prom: `/proc/net/dev` |
| `cpu_avg_pct` | observador (psutil) | Uso médio de CPU do processo WAF |
| `mem_avg_mb` | observador (psutil) | Uso médio de memória do processo WAF |
| `collector_cpu_avg_pct` | observador (psutil) | Uso médio de CPU do próprio observador |
| `collector_mem_avg_mb` | observador (psutil) | Uso médio de memória do próprio observador |
| `inspect_count` | waf → observador | Total de mensagens inspecionadas na execução |
| `inspect_avg_ms` | waf → observador | Tempo médio de inspeção por mensagem (ms) |
| `inspect_min_ms` | waf → observador | Tempo mínimo de inspeção (ms) |
| `inspect_max_ms` | waf → observador | Tempo máximo de inspeção (ms) |

---

## Detalhes dos Observadores

### eBPF (`observador_ebpf.py` + `ebpf_kern.c`)
- Programa BPF CO-RE pré-compilado com `clang` no entrypoint do container (`ebpf_entrypoint.sh`).
- Carregado em Python via `ctypes + libbpf.so.1` — sem BCC/LLVM no processo.
- `kprobe/tcp_sendmsg`: acumula bytes TX quando `sport == 8080` (respostas do WAF).
- `kprobe/tcp_cleanup_rbuf`: acumula bytes RX quando `sport == 8080` (requisições recebidas pelo WAF).
- Filtro `sport=8080` evita dupla contagem no loopback.
- Requer `privileged: true`, `pid: host`, `/sys/kernel/debug`, `/sys/kernel/btf`.

### sysstat (`observador_sysstat.py`)
- Lê `/proc/net/dev` (interface `lo`) a cada request UDP recebido.
- Retorna delta de bytes RX/TX em relação ao início do teste.
- Requer `pid: host`.

### Prometheus (`observador_prometheus.py`)
- Mesma lógica de coleta do sysstat.
- Expõe Gauges em `:8000/metrics` via `prometheus_client`.
- Bind do UDP :9999 feito antes do HTTP :8000 para evitar falha por TIME_WAIT entre execuções.
- Requer `pid: host`.

---

## Resultados

> Valores exibidos como **média ± IC95%** (intervalo de confiança de 95%, t de Student, α=0.05).
> Config: WORKERS=200, libbpf+CO-RE, 30 execuções por N. Coletados em 16–17/05/2026.

### N = 100.000 mensagens — 30 execuções

> DURATION ≈ 26s, 26 amostras/execução.

| Métrica | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| Tempo de resposta médio (ms) | **0.5407 ± 0.0121** | 0.6012 ± 0.0048 | 0.6205 ± 0.0046 |
| Desvio padrão (ms) | 0.0808 ± 0.0064 | **0.0797 ± 0.0048** | 0.0878 ± 0.0065 |
| CPU média WAF (%) | **52.385 ± 7.283** | 57.230 ± 0.200 | 57.044 ± 0.158 |
| Memória média WAF (MB) | 28.955 ± 0.083 | **28.106 ± 0.045** | 28.122 ± 0.046 |
| CPU média observador (%) | **0.051 ± 0.010** | 4.663 ± 6.543 | 2.373 ± 4.720 |
| Memória média observador (MB) | 15.226 ± 0.020 | **13.932 ± 0.015** | 24.822 ± 0.040 |

### N = 500.000 mensagens — 30 execuções

> DURATION ≈ 53s, 53 amostras/execução.

| Métrica | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| Tempo de resposta médio (ms) | **0.5038 ± 0.0055** | 0.5721 ± 0.0034 | 0.5844 ± 0.0042 |
| Desvio padrão (ms) | 0.0669 ± 0.0258 | **0.0587 ± 0.0028** | 0.0598 ± 0.0028 |
| CPU média WAF (%) | **107.02 ± 0.049** | 107.40 ± 0.052 | 107.42 ± 0.047 |
| Memória média WAF (MB) | 37.527 ± 0.118 | 36.454 ± 0.094 | **36.426 ± 0.095** |
| CPU média observador (%) | 3.515 ± 3.976 | **1.152 ± 2.244** | 3.484 ± 5.227 |
| Memória média observador (MB) | 15.125 ± 0.023 | **13.907 ± 0.023** | 24.831 ± 0.045 |

### N = 1.000.000 mensagens — 30 execuções

> DURATION ≈ 87s, 86 amostras/execução.

| Métrica | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| Tempo de resposta médio (ms) | **0.4885 ± 0.0039** | 0.5725 ± 0.0053 | 0.5682 ± 0.0026 |
| Desvio padrão (ms) | 0.0547 ± 0.0084 | 0.0760 ± 0.0187 | **0.0569 ± 0.0021** |
| CPU média WAF (%) | **107.985 ± 0.051** | 108.093 ± 0.088 | 108.219 ± 0.039 |
| Memória média WAF (MB) | 44.602 ± 0.250 | **42.750 ± 0.280** | 43.348 ± 0.182 |
| CPU média observador (%) | 0.819 ± 1.578 | 1.423 ± 1.945 | **0.742 ± 1.398** |
| Memória média observador (MB) | 15.138 ± 0.017 | **13.551 ± 0.028** | 24.164 ± 0.058 |

### N = 2.000.000 mensagens — 30 execuções

> DURATION ≈ 153s, 153 amostras/execução.

| Métrica | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| Tempo de resposta médio (ms) | **0.5283 ± 0.0070** | 0.5746 ± 0.0037 | 0.5932 ± 0.0042 |
| Desvio padrão (ms) | 0.0850 ± 0.0151 | **0.0626 ± 0.0060** | 0.0621 ± 0.0022 |
| CPU média WAF (%) | **107.958 ± 1.155** | 108.848 ± 0.068 | 108.671 ± 0.078 |
| Memória média WAF (MB) | **49.891 ± 0.643** | 53.869 ± 0.373 | 53.485 ± 0.447 |
| CPU média observador (%) | 0.471 ± 0.867 | **0.461 ± 0.836** | 0.801 ± 1.053 |
| Memória média observador (MB) | 15.066 ± 0.022 | **13.660 ± 0.025** | 24.197 ± 0.051 |

### Comparativo cross-N — Tempo de resposta médio (ms)

| N | eBPF | sysstat | Prometheus |
|---|------|---------|------------|
| 100.000 | **0.5407** | 0.6012 | 0.6205 |
| 500.000 | **0.5038** | 0.5721 | 0.5844 |
| 1.000.000 | **0.4885** | 0.5725 | 0.5682 |
| 2.000.000 | **0.5283** | 0.5746 | 0.5932 |

**Observações gerais:**
- **eBPF lidera em tempo de resposta** em todos os N, com IC95 sem sobreposição a partir de N=500k.
- **Tempo de resposta do eBPF sobe de 1M para 2M**: a vantagem sobre o sysstat encolhe de 85µs (N=1M) para 47µs (N=2M). Causa não determinada — ver a seção "Revisão do texto da tese e análise dos dados (23/09/2026)" em `relatorio_projeto.md`.
- **Memória do observador**: sysstat ~14 MB, eBPF ~15 MB (libbpf, sem BCC/LLVM), Prometheus ~24 MB — estável em todos os N.
- **Memória do WAF** cresce com N (28 MB em 100k → 50 MB em 2M), reflexo do acúmulo de conexões TCP persistentes.

### Gráficos

> Gerados por `scripts/plot_results.py` a partir das médias de 30 runs. Salvos em `results/plots/`.

![Tempo de resposta por N](results/plots/tempo_resposta_por_n.png)

![Boxplot de tempo de resposta](results/plots/boxplot_tempo_resposta.png)

![Memória do observador](results/plots/memoria_observador.png)

![CPU do WAF](results/plots/cpu_waf.png)
