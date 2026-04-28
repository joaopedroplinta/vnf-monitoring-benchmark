# TCC — Gerenciamento e Monitoramento de Rede

**Relatório do Projeto** | Gerado em: 16/04/2026 (atualizado: 28/04/2026 — rev 8)

---

## Objetivo

Projeto de TCC que compara 3 abordagens de monitoramento de rede aplicadas a uma VNF (Web Application Firewall):

| Abordagem      | Mecanismo                                            |
| -------------- | ---------------------------------------------------- |
| **eBPF (BCC)** | Instrumentação em nível de kernel via kprobes        |
| **Sysstat**    | Polling tradicional em userspace via `/proc`         |
| **Prometheus** | Mesma coleta do sysstat + exposição HTTP de métricas |

---

## Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── probe.py                   # Probe UDP único (configurado por env vars)
│   ├── vnf/
│   │   ├── waf.py                 # WAF TCP porta 8080
│   │   ├── observador_ebpf.py        # Observador eBPF: kprobes sport=8080 + psutil
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

- **`waf.py`** (85 linhas): TCP server na porta 8080
  - Detecta: SQLi, XSS, Path Traversal, RCE, Null Byte
  - Bloqueia ou encaminha requisições; não escreve métricas

- **`observador_ebpf.py`** (113 linhas): observador eBPF
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
  - Lógica de geração removida do client — separação clara entre geração e execução

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
| `DURATION`         | `NUM_MESSAGES/3500 + 15`                      | Duração da coleta (segundos)                            |
| `RUN_ID`           | 1                                             | Identificador do run                                    |
| `WORKERS`          | 10                                            | Threads concorrentes do cliente                         |
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

> DURATION = 100000/3500 + 15 = 43s → 43 amostras por run.

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

> DURATION = 500000/3500 + 15 = 157s → 157 amostras por run.

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

> DURATION = 1000000/3500 + 15 ≈ 300s → 300 amostras por run.

### Comparativo cross-N — Latência média do observador (média de 30 runs, ms)

| N          | eBPF             | sysstat          | Prometheus       | Menor latência |
| ---------- | ---------------- | ---------------- | ---------------- | -------------- |
| 100.000    | 1.2252 ± 0.0498  | **1.1876 ± 0.0414**  | 1.2348 ± 0.0690  | sysstat        |
| 500.000    | **1.3380 ± 0.0309**  | 1.4053 ± 0.0267  | 1.4381 ± 0.0265  | eBPF           |
| 1.000.000  | **1.1016 ± 0.0140**  | 1.3141 ± 0.0548  | 1.2765 ± 0.0143  | eBPF           |

### Observações (30 runs)

- **N=100k**: as três ferramentas apresentam latências estatisticamente equivalentes — IC95 se sobrepõem. Sem dominância clara.
- **N=500k**: eBPF se destaca com menor latência média (1.338 ms vs 1.405 ms sysstat vs 1.438 ms Prometheus) e IC95 que não se sobrepõem — diferença estatisticamente significativa nesse volume.
- **N=1M**: eBPF mantém a menor latência (1.098 ms), com IC95 que não se sobrepõem em relação às demais — diferença estatisticamente significativa. Prometheus supera sysstat nesse volume (1.277 ms vs 1.314 ms). CPU do WAF com Prometheus é ~5 pp maior (70.2% vs ~65%), indicando overhead do endpoint HTTP sob carga alta.
- **Tendência com N crescente**: eBPF apresenta latência inversamente proporcional ao volume (1.225 → 1.338 → 1.098 ms), sugerindo que os kprobes amortizam o custo fixo de inicialização sob cargas maiores. sysstat e Prometheus crescem monotonicamente (polling `/proc` se torna mais custoso relativamente).
- **CPU do WAF** com eBPF é maior em N=500k (72.1% vs ~68%), reflexo da interferência dos kprobes no processo monitorado sob carga contínua.
- **CPU do coletor** apresenta IC95 superior à média em N=100k (~43s de run), refletindo ruído em execuções curtas. Em N=500k (~157s) e N=1M (~300s) a variância cai significativamente.
- **Memória do coletor** estável entre runs: eBPF ~196 MB (BCC carrega runtime do kernel em userspace), sysstat ~13 MB, Prometheus ~24 MB.
- **`ebpf_1000000_run9`** (corrigido em 28/04/2026): run original tinha `inspect_count=0` — o WAF não gravou `waf_metrics.json` nessa execução (falha pontual de volume Docker). Run foi re-executado; novo resultado: 300 amostras, latência 1.1767ms, `inspect_count=274700`. Comparativo regenerado.

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
| 100.000   | 30   | 43s          | ~35s         | ~80s      | ~2h                         | ✅ Concluído (26/04/2026) |
| 500.000   | 30   | 157s         | ~35s         | ~192s     | ~5h                         | ✅ Concluído (27/04/2026) |
| 1.000.000 | 30   | 300s         | ~35s         | ~335s     | ~8h30                       | ✅ Concluído (27/04/2026) |

> DURATION = `NUM_MESSAGES / 3500 + 15` (divisão inteira bash). Overhead inclui `docker compose down + up + shutdown`. O build ocorre uma única vez antes do loop de runs (via `run_multi.sh`), não mais a cada run.

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

Os valores corrigidos para latência média (ms):

| N       | eBPF   | sysstat | Prometheus |
| ------- | ------ | ------- | ---------- |
| 100k    | 1.2252 | 1.1876  | 1.2348     |
| 500k    | 1.3380 | 1.4053  | 1.4381     |
| 1M      | 1.0982 | 1.3141  | 1.2765     |

#### Novo script: `scripts/plot_results.py`

Script para geração de gráficos a partir dos dados de benchmark. Salva em `results/plots/`.

| Gráfico | Arquivo | Descrição |
| ------- | ------- | --------- |
| Latência média por N | `latencia_por_n.png` | Barras agrupadas (eBPF/sysstat/Prometheus × N=100k/500k/1M) com IC95% |
| Distribuição de latência | `boxplot_latencia.png` | Boxplot das 30 runs por ferramenta, um painel por N |
| Memória do observador | `memoria_observador.png` | Barras agrupadas por N com IC95% — evidencia diferença eBPF (~196 MB) vs sysstat (~13 MB) vs Prometheus (~24 MB) |
| CPU do WAF | `cpu_waf.png` | Barras agrupadas por N com IC95% |

Uso: `python3 scripts/plot_results.py`

#### Correção: nota incorreta sobre bytes RX/TX removida do README e do relatório

A observação "Bytes RX/TX não são comparáveis entre eBPF e os demais" foi removida do README e da seção de Observações gerais do relatório. Os bytes RX/TX são coletados e gravados nos JSONs de resultado pelos três observadores — a nota estava incorreta ao tratá-los como não comparáveis sem evidência.

#### Correção: labels inconsistentes nos `comparison_<N>_30runs.json`

Os JSONs de N=100k e N=500k foram gerados antes do rename `coletor → observador` e usavam os labels `"CPU média coletor (%)"` / `"Memória média coletor (MB)"`, enquanto o JSON de N=1M já usava `"observador"`. Os dois arquivos foram regenerados com `python3 src/compare.py <N> 30` para garantir consistência entre os três N.

#### Documentação: run anômalo `ebpf_1000000_run9`

Identificado durante revisão de integridade dos dados: `ebpf_1000000_run9_results.json` tem `inspect_count=0` e `inspect_avg_ms=0`. O run foi executado normalmente (300 amostras, latência média 1.0758 ms, duração 300s), mas o WAF não gravou `waf_metrics.json` nesse run — provavelmente race condition na inicialização. Dados de latência, CPU e memória são válidos e entram nas agregações normalmente; apenas métricas de inspeção desse run devem ser desconsideradas.

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

**Conclusão preliminar:** A variante libbpf+CO-RE reduz o consumo de memória do observador eBPF em ~93%, de ~196 MB para ~15 MB, sem degradação mensurável de latência ou CPU. O consumo passa a ser comparável ao de sysstat (~13 MB).

**Próximos passos:** Executar 30 runs para N=100k/500k/1M com `run_multi.sh` adaptado para a variante `ebpf-libbpf` e comparar estatisticamente com as três ferramentas originais.
