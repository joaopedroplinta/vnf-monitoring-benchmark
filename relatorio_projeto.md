# TCC — Gerenciamento e Monitoramento de Rede

**Relatório do Projeto** | Gerado em: 16/04/2026 (atualizado: 16/05/2026 — rev 10)

---

## Objetivo

Projeto de TCC que compara 3 abordagens de monitoramento de rede aplicadas a uma VNF (Web Application Firewall):

| Abordagem              | Mecanismo                                            |
| ---------------------- | ---------------------------------------------------- |
| **eBPF (libbpf+CO-RE)** | Instrumentação em nível de kernel via kprobes       |
| **Sysstat**            | Polling tradicional em userspace via `/proc`         |
| **Prometheus**         | Mesma coleta do sysstat + exposição HTTP de métricas |

---

## Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── probe.py                   # Probe UDP único (configurado por env vars)
│   ├── vnf/
│   │   ├── waf.py                 # WAF TCP porta 8080
│   │   ├── observador_ebpf.py        # Observador eBPF (libbpf+CO-RE): kprobes sport=8080 + psutil (~15 MB RSS)
│   │   ├── observador_sysstat.py     # Observador sysstat: /proc/net/dev + psutil
│   │   └── observador_prometheus.py  # Observador Prometheus: /proc/net/dev + psutil + HTTP :8000
│   ├── client/
│   │   └── client.py              # Carrega payloads de PAYLOADS_FILE e os envia ao WAF
│   └── compare.py                 # Consolida resultados em CSV e JSON
├── configs/
│   ├── Dockerfile                 # Ubuntu 24.04 + BCC tools + Python 3
│   └── Dockerfile.client          # Python 3.9 slim
├── data/
│   └── payloads/                  # Arquivos binários de payloads pré-gerados
│       ├── payloads_100000_6040.bin
│       ├── payloads_500000_6040.bin
│       └── payloads_1000000_6040.bin
├── docker-compose.ebpf.yml        # Stack isolada eBPF
├── docker-compose.sysstat.yml     # Stack isolada Sysstat
├── docker-compose.prometheus.yml  # Stack isolada Prometheus
├── scripts/
│   ├── gen_payloads.py            # Gera arquivos de payloads para data/payloads/
│   ├── run_ebpf.sh                # Executa benchmark eBPF completo
│   ├── run_sysstat.sh             # Executa benchmark Sysstat completo
│   ├── run_prometheus.sh          # Executa benchmark Prometheus completo
│   └── run_multi.sh               # Executa N repetições de um benchmark
└── results/
    ├── <ferramenta>_<N>_run<ID>_results.json
    ├── comparison_<N>_<RUNS>runs.csv/.json
    └── comparison_all_runs.csv/.json
```

---

## Componentes Implementados

### 1. VNF — Web Application Firewall (`src/vnf/`)

- **`waf.py`**: TCP server na porta 8080 — `asyncio` + `ThreadPoolExecutor`
  - Detecta: SQLi, XSS, Path Traversal, RCE, Null Byte
  - Protocolo: framing com 4 bytes big-endian de comprimento; conexões persistentes (múltiplas mensagens por conexão)
  - Inspeção CPU-bound executada no pool de threads; I/O gerenciado pelo event loop asyncio

- **`observador_ebpf.py`** (181 linhas): observador eBPF (libbpf+CO-RE)
  - Carrega `ebpf_kern.o` pré-compilado via `ctypes + libbpf.so.1` — sem BCC/LLVM em memória (~15 MB RSS)
  - Kprobes em `tcp_sendmsg` e `tcp_cleanup_rbuf`, filtro `sport=8080`
  - Coleta bytes RX/TX + CPU/mem do WAF via psutil
  - Responde a probes UDP na porta 9999 com JSON de métricas

- **`observador_sysstat.py`** (83 linhas): observador sysstat
  - Lê `/proc/net/dev` (interface `lo`)
  - Coleta CPU/mem do WAF via psutil
  - Responde a probes UDP na porta 9999

- **`observador_prometheus.py`** (100 linhas): observador Prometheus
  - Mesma lógica do sysstat
  - Expõe Gauges adicionais em `:8000/metrics` via `prometheus_client`

### 2. Probe (`src/probe.py`)

- Script único compartilhado pelos três stacks
- Aguarda o observador estar pronto (`wait_ready`) antes de iniciar a medição
- Envia requisição UDP ao observador a cada 1s
- Mede RTT (roundtrip time) como métrica principal de overhead
- Configurável via variáveis de ambiente: `COLLECTOR`, `RESULTS_PATH`, `DURATION`, `OBSERVADOR_HOST`, `OBSERVADOR_PORT`
- Handler SIGTERM registrado no início: garante que `save()` é chamado mesmo quando `docker compose down` encerra o container antes de DURATION expirar
- Saída: `results/<ferramenta>_<N>_run<ID>_results.json`

### 3. Geração de Tráfego (`src/client/` + `scripts/gen_payloads.py`)

- **`gen_payloads.py`**: script de pré-geração de payloads (executado uma vez no host)
  - Gera um arquivo binário com N payloads embaralhados, distribuição configurável (padrão 60/40)
  - Saída padrão: `data/payloads/payloads_<N>_<B><M>.bin` (ex: `payloads_100000_6040.bin`)
  - Formato: `[uint32 count] + ([uint32 len] + [bytes payload]) × N`
  - Reprodutível via `--seed` (padrão: 42)

- **`client.py`**: envia os payloads pré-gerados ao WAF
  - Carrega payloads de arquivo via `PAYLOADS_FILE` (caminho dentro do container)
  - `WORKERS` coroutines asyncio (padrão 200), cada uma com conexão persistente
  - Framing 4-byte por mensagem; fila asyncio distribui payloads entre os workers

### 4. Comparação (`src/compare.py`)

Três modos de uso:

| Comando                        | Descrição                                | Saída                            |
| ------------------------------ | ---------------------------------------- | -------------------------------- |
| `python3 src/compare.py 100`   | Compara 3 ferramentas para N=100 (run 1) | `comparison_100.csv/.json`       |
| `python3 src/compare.py 100 5` | Agrega 5 runs de N=100 (média ± desvio)  | `comparison_100_5runs.csv/.json` |
| `python3 src/compare.py`       | Cross-N com todos os valores disponíveis | `comparison_all_runs.csv/.json`  |

- Respeita `RESULTS_SUBDIR` para leitura/escrita em subdiretórios (ex: `pre_testes/`)
- Pré-carrega cada arquivo uma única vez antes do loop de métricas — evita warnings duplicados

---

## Infraestrutura Docker

Três stacks independentes com topologia idêntica:

```
Cliente TCP → WAF (porta 8080) → Observador (UDP :9999)
                                         ↑
                                  probe.py (1 req/s)
```

| Stack                | Configuração                                           |
| -------------------- | ------------------------------------------------------ |
| eBPF                 | `privileged: true`, `pid: host`, BPF filesystem mounts |
| sysstat / Prometheus | unprivileged, `/proc` montado read-only, `pid: host`   |

Variáveis de ambiente relevantes:

| Variável           | Padrão                                        | Descrição                                               |
| ------------------ | --------------------------------------------- | ------------------------------------------------------- |
| `NUM_MESSAGES`     | 100000                                        | Quantidade de mensagens — usada para DURATION e naming  |
| `DURATION`         | `NUM_MESSAGES/8000 + 20`                      | Duração da coleta (segundos)                            |
| `RUN_ID`           | 1                                             | Identificador do run                                    |
| `WORKERS`          | 200                                           | Conexões assíncronas do cliente (coroutines asyncio)    |
| `PAYLOADS_FILE`    | `/app/payloads/payloads_<NUM_MESSAGES>_6040.bin` | Caminho do arquivo de payloads dentro do container    |
| `PAYLOADS_FILE_HOST` | `data/payloads/payloads_<NUM_MESSAGES>_6040.bin` | Caminho no host (sobrescreve o padrão derivado)      |
| `RESULTS_SUBDIR`   | (vazio)                                       | Subdiretório de resultados (ex: `pre_testes`)           |

---

## Resultados preliminares (18/04/2026) — 5 runs, pré-testes

> Arquivos em `results/pre_testes/`. Valores exibidos como média ± desvio padrão entre runs.

### N = 100.000 mensagens

| Métrica                    | eBPF               | sysstat              | Prometheus              |
| -------------------------- | ------------------ | -------------------- | ----------------------- |
| Latência média (ms)        | **0.8039 ± 0.043** | 0.8995 ± 0.118       | 1.0924 ± 0.160          |
| Desvio padrão (ms)         | **0.3922 ± 0.160** | 0.5672 ± 0.324       | 0.7512 ± 0.297          |
| CPU média WAF (%)          | 70.998 ± 0.611     | **66.828 ± 1.253**   | 78.182 ± 5.143          |
| Memória média observador (MB) | 196.458 ± 0.314    | **13.704 ± 0.050**   | 24.596 ± 0.162          |

### N = 500.000 mensagens

| Métrica                    | eBPF               | sysstat              | Prometheus              |
| -------------------------- | ------------------ | -------------------- | ----------------------- |
| Latência média (ms)        | **0.7691 ± 0.037** | 0.8374 ± 0.016       | 0.9531 ± 0.069          |
| Desvio padrão (ms)         | 0.5447 ± 0.140     | **0.5130 ± 0.093**   | 0.5694 ± 0.173          |
| CPU média WAF (%)          | 51.758 ± 0.471     | **50.728 ± 0.378**   | 67.384 ± 8.324          |
| Memória média observador (MB) | 196.182 ± 0.325    | **13.504 ± 0.062**   | 24.502 ± 0.125          |

---

## Resultados oficiais (26/04/2026) — 30 runs

> Arquivos em `results/`. Valores exibidos como **média ± IC95%** (intervalo de confiança de 95% — t de Student, α=0.05).

### N = 100.000 mensagens — 30 runs

| Métrica                    | eBPF (média ± IC95)    | sysstat (média ± IC95)  | Prometheus (média ± IC95) |
| -------------------------- | ---------------------- | ----------------------- | ------------------------- |
| Latência média (ms)        | 1.2252 ± 0.0498        | **1.1876 ± 0.0414**     | 1.2348 ± 0.0690           |
| Desvio padrão (ms)         | 0.9003 ± 0.1402        | **0.8323 ± 0.1306**     | 0.8647 ± 0.1148           |
| Latência máx (ms)          | 5.5523 ± 0.9028        | 5.2487 ± 0.8089         | **5.0872 ± 0.6464**       |
| Latência mín (ms)          | 0.5307 ± 0.0148        | 0.5265 ± 0.0226         | **0.4997 ± 0.0332**       |
| CPU média WAF (%)          | **66.311 ± 2.2258**    | 70.008 ± 0.1606         | 68.356 ± 3.2806           |
| Memória média WAF (MB)     | 12.194 ± 0.0147        | **12.155 ± 0.0200**     | 12.220 ± 0.0206           |
| CPU média observador (%)      | 1.927 ± 2.6211         | 2.860 ± 4.2246          | **1.402 ± 1.8656**        |
| Memória média observador (MB) | 196.474 ± 0.2631       | **13.689 ± 0.0292**     | 24.559 ± 0.0563           |

> DURATION = 100000/8000 + 20 = 32s → 32 amostras por run.

### N = 500.000 mensagens — 30 runs (27/04/2026)

| Métrica                    | eBPF (média ± IC95)    | sysstat (média ± IC95)  | Prometheus (média ± IC95) |
| -------------------------- | ---------------------- | ----------------------- | ------------------------- |
| Latência média (ms)        | **1.3380 ± 0.0309**    | 1.4053 ± 0.0267         | 1.4381 ± 0.0265           |
| Desvio padrão (ms)         | **0.9469 ± 0.0861**    | 1.0322 ± 0.0748         | 1.0469 ± 0.0772           |
| Latência máx (ms)          | 7.7065 ± 1.0172        | 7.8964 ± 0.8772         | **7.7276 ± 0.9048**       |
| Latência mín (ms)          | **0.4412 ± 0.0264**    | 0.5098 ± 0.0118         | 0.5102 ± 0.0106           |
| CPU média WAF (%)          | 72.1337 ± 0.1761       | 68.3013 ± 0.2223        | **67.4517 ± 0.2249**      |
| Memória média WAF (MB)     | **12.197 ± 0.0245**    | 12.1983 ± 0.0222        | 12.2103 ± 0.0175          |
| CPU média observador (%)      | **0.709 ± 0.8764**     | 0.749 ± 0.9423          | 0.978 ± 1.0451            |
| Memória média observador (MB) | 196.712 ± 0.3179       | **13.639 ± 0.0242**     | 24.606 ± 0.0543           |

> DURATION = 500000/8000 + 20 = 82s → 82 amostras por run.

### N = 1.000.000 mensagens — 30 runs (27/04/2026)

| Métrica                       | eBPF (média ± IC95)    | sysstat (média ± IC95)  | Prometheus (média ± IC95) |
| ----------------------------- | ---------------------- | ----------------------- | ------------------------- |
| Latência média (ms)           | **1.1016 ± 0.0140**    | 1.3141 ± 0.0548         | 1.2765 ± 0.0143           |
| Desvio padrão (ms)            | **0.7118 ± 0.0324**    | 0.8379 ± 0.0693         | 0.7442 ± 0.0347           |
| Latência máx (ms)             | **6.0817 ± 0.2919**    | 7.3840 ± 0.8908         | 6.5889 ± 0.5932           |
| Latência mín (ms)             | 0.3854 ± 0.0140        | **0.3333 ± 0.0299**     | 0.5218 ± 0.0461           |
| CPU média WAF (%)             | **65.1473 ± 0.2609**   | 65.8940 ± 0.5843        | 70.1823 ± 0.5326          |
| Memória média WAF (MB)        | 12.2693 ± 0.0206       | **12.2390 ± 0.0270**    | 12.2963 ± 0.0230          |
| CPU média observador (%)      | 0.2943 ± 0.4334        | **0.1693 ± 0.1468**     | 0.2753 ± 0.2461           |
| Memória média observador (MB) | 196.5243 ± 0.2452      | **13.6733 ± 0.0364**    | 24.5493 ± 0.0494          |

> DURATION = 1000000/8000 + 20 = 145s → 145 amostras por run.

### Comparativo cross-N — Tempo de resposta médio do observador (média de 30 runs, ms)

| N          | eBPF             | sysstat          | Prometheus       | Menor tempo de resposta |
| ---------- | ---------------- | ---------------- | ---------------- | ----------------------- |
| 100.000    | 1.2252 ± 0.0498  | **1.1876 ± 0.0414**  | 1.2348 ± 0.0690  | sysstat        |
| 500.000    | **1.3380 ± 0.0309**  | 1.4053 ± 0.0267  | 1.4381 ± 0.0265  | eBPF           |
| 1.000.000  | **1.1016 ± 0.0140**  | 1.3141 ± 0.0548  | 1.2765 ± 0.0143  | eBPF           |

### Observações (30 runs)

- **N=100k**: as três ferramentas apresentam tempos de resposta estatisticamente equivalentes — IC95 se sobrepõem. Sem dominância clara.
- **N=500k**: eBPF se destaca com menor tempo de resposta médio (1.338 ms vs 1.405 ms sysstat vs 1.438 ms Prometheus) e IC95 que não se sobrepõem — diferença estatisticamente significativa nesse volume.
- **N=1M**: eBPF mantém o menor tempo de resposta (1.098 ms), com IC95 que não se sobrepõem em relação às demais — diferença estatisticamente significativa. Prometheus supera sysstat nesse volume (1.277 ms vs 1.314 ms). CPU do WAF com Prometheus é ~5 pp maior (70.2% vs ~65%), indicando overhead do endpoint HTTP sob carga alta.
- **Tendência com N crescente**: eBPF apresenta tempo de resposta inversamente proporcional ao volume (1.225 → 1.338 → 1.098 ms), sugerindo que os kprobes amortizam o custo fixo de inicialização sob cargas maiores. sysstat e Prometheus crescem monotonicamente (polling `/proc` se torna mais custoso relativamente).
- **CPU do WAF** com eBPF é maior em N=500k (72.1% vs ~68%), reflexo da interferência dos kprobes no processo monitorado sob carga contínua.
- **CPU do coletor** apresenta IC95 superior à média em N=100k (~43s de run), refletindo ruído em execuções curtas. Em N=500k (~157s) e N=1M (~300s) a variância cai significativamente.
- **Memória do coletor** estável entre runs: eBPF ~196 MB (BCC carrega runtime do kernel em userspace), sysstat ~13 MB, Prometheus ~24 MB.
- **`ebpf_1000000_run9`** (corrigido em 28/04/2026): run original tinha `inspect_count=0` — o WAF não gravou `waf_metrics.json` nessa execução (falha pontual de volume Docker). Run foi re-executado; novo resultado: 300 amostras, tempo de resposta 1.1767ms, `inspect_count=274700`. Comparativo regenerado.

---

## Scripts de Execução

**Passo 0 — gerar os arquivos de payloads (uma vez, antes de qualquer teste):**

```bash
python3 scripts/gen_payloads.py 100000   # → data/payloads/payloads_100000_6040.bin
python3 scripts/gen_payloads.py 500000   # → data/payloads/payloads_500000_6040.bin
python3 scripts/gen_payloads.py 1000000  # → data/payloads/payloads_1000000_6040.bin

# Distribuição customizada (ex: 70% limpos / 30% maliciosos):
python3 scripts/gen_payloads.py 100000 --ratio 70
```

**Passo 1 — rodar os benchmarks normalmente:**

```bash
# Run único
NUM_MESSAGES=100000 bash scripts/run_ebpf.sh
NUM_MESSAGES=100000 bash scripts/run_sysstat.sh

# Múltiplas repetições (sequencial, salva cada run separado)
bash scripts/run_multi.sh ebpf       100000 5
bash scripts/run_multi.sh sysstat    100000 5
bash scripts/run_multi.sh prometheus 100000 5

# Resultados preliminares (salvos em results/pre_testes/)
bash scripts/run_multi.sh prometheus 100000 5 --pre
```

Os scripts `run_*.sh` derivam `PAYLOADS_FILE` automaticamente a partir de `NUM_MESSAGES` e validam que o arquivo existe antes de subir os containers. Para usar um arquivo de distribuição diferente, sobrescreva `PAYLOADS_FILE_HOST`:

```bash
PAYLOADS_FILE_HOST=data/payloads/payloads_100000_7030.bin NUM_MESSAGES=100000 bash scripts/run_ebpf.sh
```

Nomenclatura dos resultados: `<ferramenta>_<N>_run<ID>_results.json`

Os scripts `run_*.sh` aguardam o container do coletor terminar via `docker wait` (sem sleep fixo) e imprimem os logs do coletor caso o arquivo de resultado não seja encontrado.

---

## Estado Atual

- Branch: `dev/joao`
- Arquitetura: `probe.py` único + observador por variante

### Correções aplicadas (17/04/2026)

| Componente              | Problema                                                                                   | Correção                                                                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `probe.py`              | `docker compose down` encerrava o container antes de salvar                                | Handler SIGTERM registrado: `signal.signal(SIGTERM, lambda *_: sys.exit(0))` dispara o bloco `finally` com `save()`      |
| `observador_prometheus.py` | Porta HTTP 8000 em TIME_WAIT bloqueava o bind do UDP 9999, zerando amostras nos runs pares | UDP 9999 vinculado **antes** do HTTP 8000; HTTP com 30 tentativas (×2s) e fallback sem crash                             |
| `compare.py`            | Warnings de arquivo não encontrado repetindo N×TOOLS×RUNS vezes                            | Dados pré-carregados por `(tool, run_id)` fora do loop de métricas                                                       |
| `run_*.sh`              | `sleep` fixo subestimava/superestimava o tempo; falhas silenciosas                         | `docker wait <collector>` substitui o sleep; resultado verificado explicitamente com logs do coletor em caso de ausência |
| `run_multi.sh`          | Sem suporte a subdiretório de resultados                                                   | Flag `--pre` redireciona para `results/pre_testes/` via `RESULTS_SUBDIR`                                                 |
| `run_*.sh`              | `docker compose down --volumes` apagava dados entre runs                                   | Removido `--volumes`; apenas `--remove-orphans`                                                                          |

### Refatoração do cliente (23/04/2026)

Separação da geração de payloads do cliente TCP em script independente.

**Motivação:** o cliente gerava mensagens dinamicamente a cada execução (com `random.seed(42)`). A geração embutida no cliente tornava difícil variar o volume de mensagens de forma controlada e acoplava a lógica de geração ao fluxo de execução dos testes.

**Mudanças aplicadas:**

| Componente | Antes | Depois |
| --------- | ----- | ------ |
| `src/client/client.py` | Gerava payloads em memória via `build_sequence()` com `random.seed(42)`; controlado por `NUM_MESSAGES` | Carrega payloads de arquivo binário via `load_payloads()`; controlado por `PAYLOADS_FILE` |
| `scripts/gen_payloads.py` | Não existia | Novo script: gera `data/payloads/payloads_<N>_<B><M>.bin`; aceita `--ratio`, `--seed`, `--out` |
| `docker-compose.*.yml` (serviço `client`) | `NUM_MESSAGES` no environment; sem volume de payloads | `PAYLOADS_FILE` no environment; volume `./data/payloads:/app/payloads:ro` adicionado |
| `scripts/run_*.sh` | Exportava `NUM_MESSAGES` para o client | Deriva `PAYLOADS_FILE` a partir de `NUM_MESSAGES`; valida existência do arquivo antes de subir containers; exporta `PAYLOADS_FILE` |

`NUM_MESSAGES` continua presente nos scripts exclusivamente para: cálculo de `DURATION`, nomenclatura dos arquivos de resultado e argumento do `compare.py`.

### Outras mudanças (23/04/2026)

| Componente | Mudança |
| ---------- | ------- |
| `src/vnf/waf.py` | Removido loop de busy-wait desnecessário (`for i in range(1000): x += i * i`) da função `inspect()`. O resultado nunca era usado; o loop apenas inflava artificialmente a CPU do WAF, distorcendo as métricas de overhead dos coletores. |
| `src/compare.py` | Adicionada coluna de intervalo de confiança de 95% nos relatórios de múltiplos runs. Calculado como `±t × (stddev / √N)` com distribuição t de Student, permitindo comparação estatística entre as ferramentas além da média ± desvio padrão. |
| `src/vnf/waf.py` + observadores + `probe.py` | Instrumentação do tempo de inspeção da VNF (detalhado abaixo). |

### Instrumentação do tempo de inspeção da VNF (23/04/2026)

O WAF não media o tempo gasto em `inspect()`. Para quantificar o overhead de inspeção de payload por mensagem, foi adicionada instrumentação em três camadas:

**Fluxo de dados:**
```
waf.py: time.perf_counter() em torno de inspect()
    → acumula count/total/min/max (thread-safe, lock)
    → grava /app/results/waf_metrics.json a cada 100 inspeções

observador_*.py: lê waf_metrics.json ao responder cada probe UDP
    → inclui inspect_count/avg/min/max no JSON de resposta

probe.py: captura os campos no sample por iteração
    → no save(), usa o último sample (stats cumulativas)
```

**Campos adicionados ao JSON de resultado:**

| Campo | Descrição |
| ----- | --------- |
| `inspect_count` | Total de payloads inspecionados pelo WAF no run |
| `inspect_avg_ms` | Tempo médio de inspeção (ms) — cumulativo até o último sample |
| `inspect_min_ms` | Tempo mínimo de inspeção (ms) |
| `inspect_max_ms` | Tempo máximo de inspeção (ms) |

**Decisões de implementação:**
- Gravação a cada 100 inspeções (não a cada mensagem) para evitar contenção em disco durante carga alta
- Stats cumulativas: o `probe.py` usa o último sample, que reflete o estado mais completo do run
- Caminho configurável via `WAF_METRICS_PATH` (padrão: `/app/results/waf_metrics.json`), que é o volume compartilhado entre os containers WAF e observador

### Correções de robustez (26/04/2026)

Revisão do código identificou três problemas que podiam comprometer a integridade dos dados coletados:

| Componente | Problema | Correção |
| ---------- | -------- | -------- |
| `src/vnf/waf.py` | `min_ms` inicializado como `float("inf")` — valor não serializável em JSON padrão, que causaria `ValueError` no `json.dump` caso o flush fosse disparado sem nenhuma inspeção registrada | Valor inicial alterado para `None`; comparação em `_record()` ajustada para `if min_ms is None or elapsed < min_ms` |
| `src/vnf/waf.py` | Divisão por zero em `_flush()`: `total_ms / count` sem guard — inacessível no fluxo normal (flush só dispara em múltiplos de 100), mas tornava o código frágil a qualquer refatoração futura | Adicionado `if s["count"] == 0: return` no início de `_flush()` |
| `src/vnf/observador_sysstat.py`, `observador_prometheus.py` | Acesso direto a `parts[1]` e `parts[9]` no parse de `/proc/net/dev` sem verificar o comprimento do slice — `IndexError` silencioso em linha malformada ou kernel com formato diferente | Adicionado guard `if len(parts) > 9` antes do acesso |

**O que não foi alterado:** o buffer de `recvfrom` no `probe.py` já estava em 65536 bytes (suficiente para qualquer resposta JSON do observador). O cache de `_find_waf()` em `get_waf_metrics()` já existia via `_waf_proc` global — o re-scan só ocorre quando o processo morre, não a cada query.

### Robustez dos scripts de execução (26/04/2026)

Melhorias aplicadas nos três scripts `run_*.sh` para evitar falhas silenciosas durante os benchmarks:

| Mudança | Problema anterior | Efeito |
| ------- | ----------------- | ------ |
| `set -euo pipefail` adicionado ao início | Falhas em `docker compose build` ou `docker compose up` eram ignoradas — o script continuava e rodava o benchmark com a imagem antiga ou em estado inconsistente | Qualquer comando que falhe aborta o script imediatamente com código de saída não-zero |
| Validação de `NUM_MESSAGES` via regex `^[1-9][0-9]*$` | Um valor não-numérico ou zero causava erro confuso no cálculo aritmético de `DURATION`, ou gerava `PAYLOADS_FILE` com nome inválido | O script falha com mensagem clara antes de qualquer operação |
| `run_ebpf.sh` e `run_sysstat.sh`: captura de logs antes do `down` + verificação explícita do arquivo de resultado | Esses dois scripts usavam `cat ... 2>/dev/null` para exibir o resultado — arquivo ausente passava despercebido; logs do coletor eram perdidos após `docker compose down` | Comportamento agora idêntico ao `run_prometheus.sh`: logs salvos em `/tmp/collector_last_logs.txt` antes do `down`; se o JSON de resultado não existir, mensagem de erro é exibida e os logs são impressos |
| Display do resultado via `python3 -c "... open(file)"` em vez de `cat file \| python3` | Com `pipefail` ativo, o pipe `cat \| python3` falharia se o arquivo não existisse, abortando o script no ponto errado | A verificação `[ -f "$RESULT_FILE" ]` controla o fluxo; o Python lê o arquivo diretamente |

### Otimização de build no run_multi.sh (27/04/2026)

O `run_multi.sh` chamava `run_<tool>.sh` N vezes, e cada chamada executava `docker compose build` — resultando em 30 builds idênticos para código que não mudava entre runs.

**Correção aplicada:**

| Componente | Antes | Depois |
| ---------- | ----- | ------ |
| `scripts/run_multi.sh` | Não fazia build; delegava inteiramente para `run_<tool>.sh` | Executa `docker compose build` uma vez antes do loop e exporta `SKIP_BUILD=1` |
| `scripts/run_ebpf.sh`, `run_sysstat.sh`, `run_prometheus.sh` | Sempre executava `docker compose build` | Pula o build se `SKIP_BUILD=1`; comportamento inalterado quando chamado diretamente |

Quando os scripts são executados individualmente (fora do `run_multi.sh`), o build continua ocorrendo normalmente — `SKIP_BUILD` só é definido pelo `run_multi.sh`.

---

### Reorganização de resultados (26/04/2026)

Os resultados dos testes preliminares (5 runs × 100k e 500k) foram movidos de `results/` para `results/pre_testes/`, liberando `results/` para os runs oficiais do TCC.

Convenção adotada:

| Pasta | Conteúdo |
| ----- | -------- |
| `results/pre_testes/` | Testes de validação e aquecimento (runs anteriores, 5 runs por ferramenta) |
| `results/` | Dados oficiais do TCC (30 runs por ferramenta, por volume de mensagens) |

### Plano de execução dos testes oficiais

| N         | Runs | DURATION/run | Overhead/run | Tempo/run | Tempo total (3 ferramentas) | Status     |
| --------- | ---- | ------------ | ------------ | --------- | --------------------------- | ---------- |
| 100.000   | 30   | 32s          | ~35s         | ~67s      | ~1h40                       | ✅ Concluído (26/04/2026) |
| 500.000   | 30   | 82s          | ~35s         | ~117s     | ~3h                         | ✅ Concluído (27/04/2026) |
| 1.000.000 | 30   | 145s         | ~35s         | ~180s     | ~4h30                       | ✅ Concluído (27/04/2026) |

> DURATION = `NUM_MESSAGES / 8000 + 20` (divisão inteira bash). Overhead inclui `docker compose down + up + shutdown`. O build ocorre uma única vez antes do loop de runs (via `run_multi.sh`), não mais a cada run.

Comando para cada etapa (rodar uma ferramenta por vez para não perder resultados em caso de falha):
```bash
bash scripts/run_multi.sh ebpf       <N> 30
bash scripts/run_multi.sh sysstat    <N> 30
bash scripts/run_multi.sh prometheus <N> 30
```

### Resultados disponíveis

| N      | Ferramenta                | Runs | Localização           |
| ------ | ------------------------- | ---- | --------------------- |
| 100000 | eBPF, sysstat, Prometheus | 5    | `results/pre_testes/` |
| 500000 | eBPF, sysstat, Prometheus | 5    | `results/pre_testes/` |

---

### Correções e implementações (28/04/2026)

#### Correção: `compare_all_runs` usava run1 em vez das médias agregadas

O modo sem argumentos de `compare.py` (`python3 src/compare.py`) gerava `comparison_all_runs.csv/.json` carregando apenas o `run1_results.json` de cada ferramenta/N, ignorando os outros 29 runs.

**Correção aplicada:**

| Componente | Antes | Depois |
| ---------- | ----- | ------ |
| `src/compare.py` — `compare_all_runs()` | Carregava fixo `<tool>_<N>_run1_results.json` | Descobre quantos runs existem por ferramenta/N via `discover_num_runs()` e calcula a média de todos |
| `discover_runs()` | Retornava lista de N disponíveis | Renomeada para `discover_ns()` para evitar ambiguidade com "número de runs" |
| `comparison_all_runs.json` | Valores do run1 (ruidosos) | Valores de média das 30 runs — coerentes com os `comparison_<N>_30runs.json` |

Os valores corrigidos para tempo de resposta médio (ms):

| N       | eBPF   | sysstat | Prometheus |
| ------- | ------ | ------- | ---------- |
| 100k    | 1.2252 | 1.1876  | 1.2348     |
| 500k    | 1.3380 | 1.4053  | 1.4381     |
| 1M      | 1.0982 | 1.3141  | 1.2765     |

#### Novo script: `scripts/plot_results.py`

Script para geração de gráficos a partir dos dados de benchmark. Salva em `results/plots/`.

| Gráfico | Arquivo | Descrição |
| ------- | ------- | --------- |
| Tempo de resposta médio por N | `tempo_resposta_por_n.png` | Barras agrupadas (eBPF/sysstat/Prometheus × N=100k/500k/1M/2M) com IC95% |
| Distribuição do tempo de resposta | `boxplot_tempo_resposta.png` | Boxplot das 30 runs por ferramenta, um painel por N |
| Memória do observador | `memoria_observador.png` | Barras agrupadas por N com IC95% — evidencia diferença eBPF (~196 MB) vs sysstat (~13 MB) vs Prometheus (~24 MB) |
| CPU do WAF | `cpu_waf.png` | Barras agrupadas por N com IC95% |

Uso: `python3 scripts/plot_results.py`

#### Correção: nota incorreta sobre bytes RX/TX removida do README e do relatório

A observação "Bytes RX/TX não são comparáveis entre eBPF e os demais" foi removida do README e da seção de Observações gerais do relatório. Os bytes RX/TX são coletados e gravados nos JSONs de resultado pelos três observadores — a nota estava incorreta ao tratá-los como não comparáveis sem evidência.

#### Correção: labels inconsistentes nos `comparison_<N>_30runs.json`

Os JSONs de N=100k e N=500k foram gerados antes do rename `coletor → observador` e usavam os labels `"CPU média coletor (%)"` / `"Memória média coletor (MB)"`, enquanto o JSON de N=1M já usava `"observador"`. Os dois arquivos foram regenerados com `python3 src/compare.py <N> 30` para garantir consistência entre os três N.

#### Documentação: run anômalo `ebpf_1000000_run9`

Identificado durante revisão de integridade dos dados: `ebpf_1000000_run9_results.json` tem `inspect_count=0` e `inspect_avg_ms=0`. O run foi executado normalmente (300 amostras, tempo de resposta médio 1.0758 ms, duração 300s), mas o WAF não gravou `waf_metrics.json` nesse run — provavelmente race condition na inicialização. Dados de tempo de resposta, CPU e memória são válidos e entram nas agregações normalmente; apenas métricas de inspeção desse run devem ser desconsideradas.

#### Correção: código redundante em `plot_results.py`

`plot_memoria_observador()` tinha duas chamadas `find_row()` no início do loop interno que eram imediatamente sobrescritas pelo `for` seguinte. As chamadas redundantes foram removidas — comportamento inalterado.

---

### Investigação: redução de memória eBPF — BCC → libbpf+CO-RE (28/04/2026)

**Contexto:** O observador eBPF original usa BCC (`python3-bpfcc`), que carrega LLVM/Clang no processo Python em tempo de execução para compilar o programa BPF. Isso resulta em ~196 MB de RSS — significativamente acima dos ~13 MB (sysstat) e ~24 MB (Prometheus).

**Hipótese:** Pré-compilar o programa BPF com `clang` no entrypoint do container e carregá-lo em Python via `ctypes + libbpf.so.1` (sem BCC) deveria eliminar a pegada de LLVM do processo principal.

**Implementação (branch `feat/ebpf-libbpf-memory`, Issue #26):**

| Arquivo | Descrição |
| ------- | --------- |
| `src/vnf/ebpf_kern.c` | Programa BPF CO-RE com `BPF_KPROBE` + `BPF_CORE_READ` e mapa `BPF_MAP_TYPE_ARRAY` |
| `src/vnf/ebpf_entrypoint.sh` | Gera `vmlinux.h` via bpftool (BTF do kernel), compila com `clang -D__TARGET_ARCH_x86`, executa o Python |
| `src/vnf/observador_ebpf_libbpf.py` | Carrega o `.o` via `ctypes + libbpf.so.1`; mesma lógica UDP/waf_metrics do observador original |
| `configs/Dockerfile.ebpf-libbpf` | Ubuntu 24.04 **sem** `bpfcc-tools`/`python3-bpfcc`; instala apenas `libbpf1 libbpf-dev clang linux-tools-generic` |
| `docker-compose.ebpf-libbpf.yml` | Stack independente para a variante libbpf |
| `scripts/run_ebpf_libbpf.sh` | Script de benchmark equivalente ao `run_ebpf.sh` |

**Dificuldades encontradas durante a implementação:**

- O wrapper `/usr/sbin/bpftool` no Ubuntu 24.04 verifica `uname -r` e falha em kernels não-Ubuntu (ex: Manjaro 6.12). Solução: o entrypoint usa `find /usr/lib/linux-tools -name bpftool | head -1` para obter o binário real.
- A flag de arquitetura BPF deve ser `-D__TARGET_ARCH_x86` (não `x86_64`) para targets x86_64.

**Resultado do primeiro teste (N=100.000, run de validação):**

| Métrica | BCC (original) | libbpf (novo) | Variação |
| ------- | -------------- | ------------- | -------- |
| Memória observador (MB) | ~196 | **14,98** | −92% |
| Latência avg (ms) | ~1,18 | 1,20 | +1,7% |
| CPU avg (%) | ~0,1 | 0,09 | — |
| inspect_count | 53.500 | 53.500 | igual |

**Conclusão preliminar:** A variante libbpf+CO-RE reduz o consumo de memória do observador eBPF em ~93%, de ~196 MB para ~15 MB, sem degradação mensurável de tempo de resposta ou CPU. O consumo passa a ser comparável ao de sysstat (~13 MB).

**Decisão (Opção C):** Substituir o observador BCC pelo libbpf no stack principal (`docker-compose.ebpf.yml`) e re-executar todos os 90 runs (30×3 N) para manter o dataset consistente sob uma única implementação.

- `docker-compose.ebpf.yml` atualizado: observador usa `Dockerfile.ebpf-libbpf` + `ebpf_entrypoint.sh`; volumes `/lib/modules` e `/usr/src` removidos; `/sys/kernel/btf` adicionado.
- N=100k re-executado: 30 runs concluídos com libbpf em 28/04/2026.
- N=500k e N=1M: re-execução pendente.

**Resultado N=100k (30 runs libbpf, 28/04/2026):**

| Métrica | eBPF (libbpf) | sysstat | Prometheus |
| ------- | ------------- | ------- | ---------- |
| Latência média (ms) | **1.1435 ± 0.0272** | 1.1876 ± 0.0414 | 1.2348 ± 0.0690 |
| Memória observador (MB) | 15.050 ± 0.036 | **13.689 ± 0.029** | 24.559 ± 0.056 |

eBPF libbpf passa a ter memória comparável ao sysstat (~15 MB vs ~14 MB), eliminando a desvantagem estrutural dos ~196 MB do BCC.

---

### Migração para asyncio + conexões persistentes (29/04/2026)

**Contexto:** O WAF original usava uma thread por conexão TCP (modelo `threading.Thread`). O cliente abria e fechava uma conexão TCP por mensagem. O throughput observado era ~3500 msg/s e o gargalo não era a CPU, mas o overhead de handshake TCP por mensagem e a contenção de threads.

**Diagnóstico do gargalo:**

Com tempo de resposta UDP de ~1.32 ms e 10 workers, o throughput teórico máximo seria:

```
10 workers / 0.00132s = ~7576 msg/s
```

O valor observado (~3500 msg/s) indicava que o custo de abrir e fechar conexões TCP — não a inspeção — era o fator limitante.

**Mudanças implementadas (Issue #27):**

| Componente | Antes | Depois |
| ---------- | ----- | ------ |
| `src/vnf/waf.py` | `threading.Thread` por conexão; uma conexão por mensagem | `asyncio.start_server` + `ThreadPoolExecutor`; conexões persistentes com framing de 4 bytes |
| `src/client/client.py` | `ThreadPoolExecutor(max_workers=10)`; nova conexão TCP por payload | `asyncio.gather` com 200 coroutines; conexão persistente por worker; fila asyncio distribui payloads |
| `src/vnf/observador_*.py` | `_find_waf()` retornava o primeiro processo com `waf.py` no cmdline | `_find_waf_all()` retorna todos os processos com `waf.py` e agrega CPU/mem |
| `scripts/run_*.sh` | `DURATION = NUM_MESSAGES/3500 + 15` | `DURATION = NUM_MESSAGES/8000 + 20` |

**Protocolo de framing:**

```
Requisição: [4 bytes big-endian: comprimento do payload] + [payload]
Resposta:   "ALLOWED:OK\n" ou "BLOCKED:<motivo>\n"  (newline-terminated)
```

A conexão permanece aberta; o WAF lê mensagens em loop até o cliente fechar a conexão (`asyncio.IncompleteReadError`).

**Resultado medido (N=100.000, 1 run, 29/04/2026):**

| Métrica | Antes (threading) | Depois (asyncio) | Variação |
| ------- | ----------------- | ---------------- | -------- |
| Throughput | ~3500 msg/s | **~8000 msg/s** | +128% |
| Latência UDP avg (ms) | 1.32 | **0.53** | −60% |
| CPU WAF avg (%) | 70 | **37** | −47% |
| inspect_avg_ms | 0.214 | **0.089** | −58% |
| Memória WAF (MB) | 12 | 21.6 | +80% (ThreadPoolExecutor) |

O aumento de memória (~10 MB) é atribuído ao pool de threads do `ThreadPoolExecutor` (8 workers × overhead de thread Python).

**Decisão de arquitetura — observadores:**

A função `_find_waf_all()` foi introduzida nos três observadores para ser compatível com eventuais futuros modos multiprocessing do WAF: ao invés de monitorar apenas o processo pai (que ficaria idle em multiprocessing), agrega CPU e RSS de todos os processos com `waf.py` no cmdline via `psutil.process_iter`. Em modo single-process (atual), o comportamento é idêntico ao anterior.

---

### Orquestração com Claude Code — agentes e skills (14/05/2026)

Criada estrutura de agentes e skills do Claude Code em `.claude/` para automatizar e padronizar o fluxo de trabalho do projeto.

**Agentes** (`.claude/agents/`) — sub-agentes especializados invocados pelo Claude Code:

| Agente | Responsabilidade |
| ------ | ---------------- |
| `experiment-orchestrator` | Orquestra a bateria de testes: sobe docker compose por ferramenta, aguarda conclusão, derruba e consolida |
| `results-analyst` | Lê os JSONs de resultado e gera análise estatística comparativa |
| `ebpf-specialist` | Debug de problemas eBPF/BCC/kprobes — latência zero, kretprobes em WSL2, erros de compilação BPF |
| `docker-debugger` | Investiga falhas de container — portas, redes, volumes, healthcheck |
| `anomaly-investigator` | Detecta e classifica anomalias nos dados coletados (EXPECTED / ANOMALY / CRITICAL) |
| `tcc-writer` | Gera texto acadêmico em português formal (ABNT) a partir dos dados de resultado |
| `metrics-comparator` | Comparação dimensão a dimensão entre as três ferramentas com veredicto e placar |

**Slash commands** (`.claude/commands/`) — comandos disponíveis na sessão do Claude Code:

| Comando | Ação |
| ------- | ---- |
| `/validate-env` | Verifica Docker, kernel headers, BCC, portas 8080/9999 antes de rodar testes |
| `/run-experiment <tool>` | Executa um coletor específico (ebpf / sysstat / prometheus) |
| `/run-all [duration]` | Executa os três coletores em sequência e gera comparativo |
| `/check-results` | Exibe resumo rápido dos JSONs de resultado disponíveis |
| `/generate-report` | Roda `compare.py` e formata a saída |
| `/analyze-anomalies` | Investigação profunda de anomalias nos dados coletados |
| `/write-section <seção>` | Gera seção acadêmica do TCC (metodologia / resultados / discussao / conclusao / resumo) |

---

### Atualização de branches e sincronização (14/05/2026)

Branches sincronizadas com o repositório remoto:

| Branch | Situação |
| ------ | -------- |
| `main` | Pull de origin/main — 107+ commits integrados |
| `dev/joao` | Pull de origin/dev/joao — 107 commits atualizados |
| `dev/rafael` | Pull de origin/dev/rafael — 109 commits atualizados |
| `feat/ebpf-libbpf-memory` | Branch criada localmente a partir de origin — merge no main pendente |

**Pendências identificadas:**

- Merge de `feat/ebpf-libbpf-memory` no `main` — inclui libbpf+CO-RE como stack principal do eBPF e WAF asyncio
- Re-coleta de N=500k e N=1M com o stack libbpf (N=100k já concluído na branch)

---

### Streaming de payloads no cliente (14/05/2026)

**Motivação:** o cliente carregava todos os N payloads em memória antes de iniciar o envio (`load_payloads()` retornava uma lista completa). Para N=1M isso representava ~1,2 GB de RAM, tornando N=2M+ inviável por restrições de memória.

**Mudança implementada em `src/client/client.py`:**

| Componente | Antes | Depois |
| ---------- | ----- | ------ |
| Carregamento de payloads | `load_payloads()` — lista completa em memória; RAM = O(N) | `payload_producer()` — producer assíncrono via `asyncio.Queue(maxsize=QUEUE_SIZE)`; RAM = O(QUEUE_SIZE) |
| Leitura do arquivo | Feita integralmente antes do envio | Lazy: um payload por vez via `run_in_executor`, bloqueando quando a queue enche (backpressure automático) |
| Encerramento dos workers | `queue.get_nowait()` + `except QueueEmpty` | `await queue.get()` + sentinela `None` por worker |
| Variável de ambiente nova | — | `QUEUE_SIZE` (padrão: 2000) — controla o buffer em memória |

**Impacto no uso de memória:**

| N | RAM antes | RAM depois |
| - | --------- | ---------- |
| 1M | ~1,2 GB | ~2,6 MB |
| 5M | ~6,0 GB | ~2,6 MB |
| 10M | ~12 GB | ~2,6 MB |

A RAM do cliente agora é constante independente de N. O único limite para N passa a ser o espaço em disco para o arquivo `.bin` de payloads.

---

### Decisões estratégicas (14/05/2026)

**Hardware para coleta dos dados definitivos**

Os dados existentes (N=100k, 500k, 1M — 30 runs cada) foram coletados em notebook com Intel Core i5 11ª geração, sujeito a throttling térmico em runs longos. Os dados definitivos do TCC serão coletados em desktop com AMD Ryzen 5 5500 (6 cores físicos / 12 threads) rodando Ubuntu nativo, pelos seguintes motivos:

- Ausência de throttling térmico — desempenho sustentado e consistente entre runs
- Mais cores disponíveis para `WAF_INSPECT_WORKERS` — maior throughput (~15.000–20.000 msg/s estimado vs ~8.000 msg/s no notebook)
- eBPF sem limitações de WSL2 — kretprobes estáveis, latência real medida

**Consequência:** todos os 270 runs (30 × 3 ferramentas × 3 valores de N) serão re-coletados no desktop para garantir consistência do dataset.

**Próximo valor de N**

N=2.000.000 definido como próximo ponto de dados após a migração de hardware. Com throughput estimado de ~15.000 msg/s, cada run leva ~150s, resultando em ~11h para 90 runs (30 × 3 ferramentas) — viável em execução noturna.

**Número de runs**

30 runs por ferramenta por N mantidos conforme definição do orientador.

---

### Consolidação eBPF + reorganização Claude Code (15/05/2026)

#### Consolidação: libbpf como implementação única do observador eBPF

Com a migração para libbpf+CO-RE já validada (N=100k, 30 runs) e a decisão de re-coletar todos os dados no desktop, os arquivos duplicados da variante libbpf foram removidos e a implementação passou a ser única:

| Ação | Detalhe |
| ---- | ------- |
| `observador_ebpf_libbpf.py` → `observador_ebpf.py` | libbpf passa a ser a implementação canônica; versão BCC removida |
| `docker-compose.ebpf-libbpf.yml` removido | Redundante — `docker-compose.ebpf.yml` já usava `Dockerfile.ebpf-libbpf` desde a Opção C |
| `scripts/run_ebpf-libbpf.sh` removido | Redundante com `run_ebpf.sh` |
| `run_multi.sh` | Opção `ebpf-libbpf` removida; ferramentas válidas: `ebpf`, `sysstat`, `prometheus` |
| `ebpf_entrypoint.sh` | Última linha atualizada para `observador_ebpf.py`; labels de log simplificados |

#### Reorganização dos slash commands do Claude Code

Descoberta e correção: o diretório correto para slash commands no Claude Code é `.claude/commands/`, não `.claude/skills/`. A pasta foi renomeada e o CLAUDE.md atualizado.

#### Novos agentes criados

| Agente | Responsabilidade |
| ------ | ---------------- |
| `sysstat-specialist` | Debug do observador sysstat — `/proc/net/dev`, psutil, WAF metrics |
| `prometheus-specialist` | Debug do observador Prometheus — endpoint HTTP `:8000`, Gauges, port 8000 |
| `pr-opener` | Monta e abre PRs via `gh pr create`, sempre com confirmação antes de executar |
| `pr-reviewer` | Lê diff completo, emite veredicto estruturado (APROVADO / MUDANÇAS / BLOQUEADO), não submete sem confirmação |

---

### Correção crítica no cliente — incompatibilidade Python 3.9 (16/05/2026)

**Bug:** `src/client/client.py` usava `bytes | None` na assinatura de `_read_payload` (PEP 604, Python 3.10+). O `Dockerfile.client` usa Python 3.9 slim, que não suporta essa sintaxe — o container crashava com `TypeError` na importação, antes de enviar qualquer mensagem ao WAF.

**Impacto:** todos os 30 runs iniciais de N=100k coletados no desktop foram inválidos: `inspect_count=0`, `bytes_rx/tx=0`, `cpu_avg_pct=0`. O problema ficou mascarado porque o probe UDP (`src/probe.py`) opera independentemente do cliente e continuava a registrar tempos de resposta, dando falsa impressão de experimento concluído.

**Detecção:** análise cruzada de `inspect_count` e ausência de `results/waf_metrics.json` após os runs.

**Correção:** substituir `bytes | None` por `Optional[bytes]` com `from typing import Optional`.

**Consequência:** os 30 runs de N=100k foram descartados e recoletados após o fix.

---

### Correção de config e recoleta oficial N=100k e N=500k (16/05/2026)

#### Correção dos scripts de coleta

Identificado segundo problema de configuração além do bug Python 3.9: os três scripts `run_*.sh` usavam `WORKERS=10` (padrão) e fórmula de DURATION baseada em 8000 msg/s — valores de um experimento anterior com throughput muito mais baixo.

| Parâmetro | Antes (errado) | Depois (correto) |
| --------- | -------------- | ---------------- |
| `WORKERS` | 10 | 200 |
| Fórmula DURATION | `NUM_MESSAGES / 8000 + 20` | `NUM_MESSAGES / 15000 + 20` |

Com WORKERS=10, o cliente não conseguia saturar o WAF — a CPU do WAF ficava em ~50-67% em vez dos ~107% esperados para 500k mensagens. A fórmula de DURATION superestimava o tempo de coleta (ex: 82s em vez de 53s para 500k), coletando amostras com o WAF ocioso e puxando `cpu_avg_pct` artificialmente para baixo.

#### Anomalia detectada no Prometheus 500k (dados antigos)

Antes da recoleta, análise dos dados existentes de Prometheus 500k revelou valores críticos:
- Latência média: 1.438ms (vs 0.504ms eBPF) — 2.8× maior
- Desvio padrão: 1.047ms (vs ~0.06ms nas demais)
- CPU WAF: 67.5% (vs 107% nas demais)
- `inspect_count`: ~147k em vez de 500k

Root cause: os runs de Prometheus 500k foram coletados em 27/04/2026 com `WORKERS=10` e `DURATION=157s` — a config errada original. O WAF nunca foi saturado nesse stack. Todos os 30 runs foram descartados e recoletados.

#### Resultados oficiais recoletados — N=100.000 (16/05/2026)

> DURATION = 100000/15000 + 20 = 26s → 26 amostras por run. Config: WORKERS=200, libbpf+CO-RE.

| Métrica | eBPF (média ± IC95) | sysstat (média ± IC95) | Prometheus (média ± IC95) |
| ------- | ------------------- | ---------------------- | ------------------------- |
| Latência média (ms) | **0.5407 ± 0.0121** | 0.6012 ± 0.0048 | 0.6205 ± 0.0046 |
| Desvio padrão (ms) | 0.0808 ± 0.0064 | **0.0797 ± 0.0048** | 0.0878 ± 0.0065 |
| Latência máx (ms) | **0.7473 ± 0.0330** | 0.7797 ± 0.0318 | 0.8451 ± 0.0358 |
| Latência mín (ms) | **0.3632 ± 0.0196** | 0.4010 ± 0.0098 | 0.4164 ± 0.0153 |
| CPU média WAF (%) | **52.385 ± 7.283** | 57.230 ± 0.200 | 57.044 ± 0.158 |
| Memória média WAF (MB) | 28.955 ± 0.083 | **28.106 ± 0.045** | 28.122 ± 0.046 |
| CPU média observador (%) | **0.051 ± 0.010** | 4.663 ± 6.543 | 2.373 ± 4.720 |
| Memória média observador (MB) | 15.226 ± 0.020 | **13.932 ± 0.015** | 24.822 ± 0.040 |

> CPU WAF em 52% para eBPF em N=100k: carga leve — WAF não satura um core nesse volume. Valor coerente; contraste com N=500k onde todos chegam a 107%.

#### Resultados oficiais recoletados — N=500.000 (16/05/2026)

> DURATION = 500000/15000 + 20 = 53s → 53 amostras por run. Config: WORKERS=200, libbpf+CO-RE.

| Métrica | eBPF (média ± IC95) | sysstat (média ± IC95) | Prometheus (média ± IC95) |
| ------- | ------------------- | ---------------------- | ------------------------- |
| Latência média (ms) | **0.5038 ± 0.0055** | 0.5721 ± 0.0034 | 0.5844 ± 0.0042 |
| Desvio padrão (ms) | 0.0669 ± 0.0258 | **0.0587 ± 0.0028** | 0.0598 ± 0.0028 |
| Latência máx (ms) | 0.7475 ± 0.2027 | **0.7227 ± 0.0136** | 0.7417 ± 0.0200 |
| Latência mín (ms) | **0.3552 ± 0.0143** | 0.4151 ± 0.0162 | 0.4121 ± 0.0118 |
| CPU média WAF (%) | **107.02 ± 0.049** | 107.40 ± 0.052 | 107.42 ± 0.047 |
| Memória média WAF (MB) | 37.527 ± 0.118 | 36.454 ± 0.094 | **36.426 ± 0.095** |
| CPU média observador (%) | 3.515 ± 3.976 | **1.152 ± 2.244** | 3.484 ± 5.227 |
| Memória média observador (MB) | 15.125 ± 0.023 | **13.907 ± 0.023** | 24.831 ± 0.045 |

#### Permissão Docker para usuário pinguas

Usuário `pinguas` adicionado ao grupo `docker` (`sudo usermod -aG docker pinguas`) para eliminar a necessidade de `sudo` nos scripts de coleta. Requer logout/login completo para ter efeito na sessão gráfica.

#### Observações (resultados com config correta)

- **Tempos de resposta ~2× menores** que os dados anteriores (antigo: ~1.2ms; novo: ~0.5-0.6ms) — reflexo direto do WORKERS correto (200) e throughput real de ~15k msg/s
- **eBPF lidera em tempo de resposta** em ambos os N, com diferença estatisticamente significativa (IC95 sem sobreposição)
- **Sysstat tem menor footprint de memória** do observador (~13.9 MB vs 15.2 MB eBPF vs 24.8 MB Prometheus)
- **CPU do observador eBPF** praticamente zero em N=100k (0.051%) — confirma vantagem de overhead do kernel space
- **PR #30** aberto em `dev/joao → main` com os 180 runs válidos e correções de config

### Recoleta N=1M e coleta N=2M (17/05/2026)

#### Descarte dos dados antigos de N=1M

Os dados anteriores de N=1M (coletados em 27/04/2026) foram descartados por inconsistência de configuração: runs 1–12 tinham 86 samples (config antiga com DURATION menor), run 13 travou, e runs 14–30 tinham 300 samples (config nova). Dados incomparáveis para cálculo de média ± IC95%.

#### Resultados oficiais recoletados — N=1.000.000 (17/05/2026)

> DURATION = 1000000/15000 + 20 ≈ 87s → 86 amostras por run. Config: WORKERS=200, libbpf+CO-RE.

| Métrica | eBPF (média ± IC95) | sysstat (média ± IC95) | Prometheus (média ± IC95) |
| ------- | ------------------- | ---------------------- | ------------------------- |
| Latência média (ms) | **0.4885 ± 0.0039** | 0.5725 ± 0.0053 | 0.5682 ± 0.0026 |
| Desvio padrão (ms) | 0.0547 ± 0.0084 | 0.0760 ± 0.0187 | **0.0569 ± 0.0021** |
| Latência máx (ms) | **0.6789 ± 0.0928** | 0.9165 ± 0.2006 | 0.7450 ± 0.0150 |
| Latência mín (ms) | **0.3409 ± 0.0150** | 0.4000 ± 0.0132 | 0.4209 ± 0.0152 |
| CPU média WAF (%) | **107.985 ± 0.051** | 108.093 ± 0.088 | 108.219 ± 0.039 |
| Memória média WAF (MB) | 44.602 ± 0.250 | **42.750 ± 0.280** | 43.348 ± 0.182 |
| CPU média observador (%) | 0.819 ± 1.578 | 1.423 ± 1.945 | **0.742 ± 1.398** |
| Memória média observador (MB) | 15.138 ± 0.017 | **13.551 ± 0.028** | 24.164 ± 0.058 |

#### Resultados oficiais — N=2.000.000 (17/05/2026)

> DURATION = 2000000/15000 + 20 ≈ 153s → 153 amostras por run. Config: WORKERS=200, libbpf+CO-RE.

| Métrica | eBPF (média ± IC95) | sysstat (média ± IC95) | Prometheus (média ± IC95) |
| ------- | ------------------- | ---------------------- | ------------------------- |
| Latência média (ms) | **0.5283 ± 0.0070** | 0.5746 ± 0.0037 | 0.5932 ± 0.0042 |
| Desvio padrão (ms) | 0.0850 ± 0.0151 | **0.0626 ± 0.0060** | 0.0621 ± 0.0022 |
| Latência máx (ms) | 1.0622 ± 0.2253 | 0.8459 ± 0.0978 | **0.8168 ± 0.0301** |
| Latência mín (ms) | **0.3641 ± 0.0154** | 0.4184 ± 0.0165 | 0.4270 ± 0.0153 |
| CPU média WAF (%) | **107.958 ± 1.155** | 108.848 ± 0.068 | 108.671 ± 0.078 |
| Memória média WAF (MB) | **49.891 ± 0.643** | 53.869 ± 0.373 | 53.485 ± 0.447 |
| CPU média observador (%) | 0.471 ± 0.867 | **0.461 ± 0.836** | 0.801 ± 1.053 |
| Memória média observador (MB) | 15.066 ± 0.022 | **13.660 ± 0.025** | 24.197 ± 0.051 |

#### Comparativo cross-N — Latência média do observador (média de 30 runs, ms)

| N | eBPF | sysstat | Prometheus |
|---|------|---------|------------|
| 100.000 | **0.5407** | 0.6012 | 0.6205 |
| 500.000 | **0.5038** | 0.5721 | 0.5844 |
| 1.000.000 | **0.4885** | 0.5725 | 0.5682 |
| 2.000.000 | **0.5283** | 0.5746 | 0.5932 |

#### Achado relevante: overhead do eBPF escala com volume

O tempo de resposta do eBPF aumentou de N=1M para N=2M (+0.040ms, +8.2%), enquanto o sysstat permaneceu praticamente estável (+0.002ms, +0.3%). Isso ocorre porque os kprobes (`tcp_sendmsg`, `tcp_cleanup_rbuf`) disparam por pacote — com 2× o tráfego, há 2× as interrupções no kernel. O sysstat lê `/proc/net/dev` uma vez por segundo, independente do volume. A vantagem do eBPF em tempo de resposta encolheu de 85µs (N=1M) para 47µs (N=2M).

#### Correções de documentação (17/05/2026)

- **`docs/arquitetura_c4.svg`:** reformulação do diagrama C4 — fusão dos dois boxes do Observador (eBPF/sysstat/prom + UDP server) em um único contêiner, corrigindo a incoerência arquitetural do C4 Level 2; labels das setas traduzidos para português; label "C4 — Container Diagram (Nível 2)" adicionado; correção do `writing-mode` na seta interna
- **`docs/architecture.md`:** terminologia atualizada (`monitor_*.py` → `observador_*.py`, WORKERS 10 → 200, WAF multithreaded → asyncio + ThreadPoolExecutor, cliente threads → coroutines asyncio com conexões persistentes)
- **PR #30:** branch `dev/joao` recriado com cherry-pick dos 5 commits relevantes (force-push com `--force-with-lease`) para eliminar histórico de merges antigos acumulados
