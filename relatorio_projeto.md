# TCC — Gerenciamento e Monitoramento de Rede

**Relatório do Projeto** | Gerado em: 16/04/2026 (atualizado: 23/04/2026 — rev 5)

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

## Resultados (18/04/2026)

### N = 100.000 mensagens — 5 runs (média ± desvio entre runs)

| Métrica                    | eBPF (média ± dp)  | sysstat (média ± dp) | Prometheus (média ± dp) |
| -------------------------- | ------------------ | -------------------- | ----------------------- |
| Latência média (ms)        | **0.8039 ± 0.043** | 0.8995 ± 0.118       | 1.0924 ± 0.160          |
| Desvio padrão (ms)         | **0.3922 ± 0.160** | 0.5672 ± 0.324       | 0.7512 ± 0.297          |
| Latência máx (ms)          | **2.4065 ± 1.243** | 3.1361 ± 1.797       | 4.4650 ± 1.526          |
| Latência mín (ms)          | 0.4033 ± 0.056     | **0.2755 ± 0.061**   | 0.4890 ± 0.124          |
| Amostras coletadas         | 43 ± 0             | 43 ± 0               | 43 ± 0                  |
| CPU média WAF (%)          | 70.998 ± 0.611     | **66.828 ± 1.253**   | 78.182 ± 5.143          |
| Memória média WAF (MB)     | 11.738 ± 0.023     | **11.648 ± 0.066**   | 11.808 ± 0.066          |
| CPU média coletor (%)      | **0.104 ± 0.093**  | 0.108 ± 0.097        | 0.088 ± 0.035           |
| Memória média coletor (MB) | 196.458 ± 0.314    | **13.704 ± 0.050**   | 24.596 ± 0.162          |

> Nota: DURATION = 100000/3500 + 15 ≈ 43s → 43 amostras por run.

### N = 500.000 mensagens — 5 runs (média ± desvio entre runs)

| Métrica                    | eBPF (média ± dp)  | sysstat (média ± dp) | Prometheus (média ± dp) |
| -------------------------- | ------------------ | -------------------- | ----------------------- |
| Latência média (ms)        | **0.7691 ± 0.037** | 0.8374 ± 0.016       | 0.9531 ± 0.069          |
| Desvio padrão (ms)         | 0.5447 ± 0.140     | **0.5130 ± 0.093**   | 0.5694 ± 0.173          |
| Latência máx (ms)          | 5.2284 ± 1.584     | 4.7667 ± 1.181       | **4.6328 ± 1.399**      |
| Latência mín (ms)          | 0.2804 ± 0.056     | **0.2757 ± 0.040**   | 0.3025 ± 0.084          |
| Amostras coletadas         | 157 ± 0            | 157 ± 0              | 157 ± 0                 |
| CPU média WAF (%)          | 51.758 ± 0.471     | **50.728 ± 0.378**   | 67.384 ± 8.324          |
| Memória média WAF (MB)     | 11.722 ± 0.036     | **11.664 ± 0.076**   | 11.816 ± 0.046          |
| CPU média coletor (%)      | **0.056 ± 0.006**  | 2.530 ± 5.523        | 2.906 ± 6.319           |
| Memória média coletor (MB) | 196.182 ± 0.325    | **13.504 ± 0.062**   | 24.502 ± 0.125          |

> Nota: DURATION = 500000/3500 + 15 ≈ 157s → 157 amostras por run.

### Observações

- **eBPF** tem a menor latência média em ambos os N — overhead de coleta mais baixo sob carga alta, apesar do custo de setup do kprobe.
- **Memória do coletor eBPF ~196 MB** vs sysstat ~13 MB e Prometheus ~24 MB: custo do BCC carregar o runtime do kernel em espaço de usuário.
- **CPU do coletor eBPF** é extremamente baixa (< 0.1%) porque a coleta ocorre no kernel; sysstat e Prometheus têm variância alta em N=500k (std > 5%), possivelmente por variações no polling de `/proc`.
- **Prometheus** apresenta maior variância na CPU do WAF em N=500k (±8.3%) e na latência, reflexo do custo adicional do servidor HTTP em `:8000/metrics`.
- **Bytes RX/TX não são comparáveis entre eBPF e sysstat/Prometheus** por diferença no ponto de medição. O observador eBPF intercepta as chamadas de sistema `tcp_sendmsg` e `tcp_cleanup_rbuf` via kprobes com filtro `sport=8080`, contabilizando exclusivamente o tráfego TCP do WAF. Já sysstat e Prometheus leem `/proc/net/dev` na interface `lo`, que agrega _todo_ o tráfego da loopback — incluindo as probes UDP na porta 9999 e qualquer outro tráfego da máquina. Comparar os bytes reportados pelas duas abordagens equivale a comparar medições de escopos distintos.

---

## Pendências e Decisões em Aberto

### Loop de busy-wait no `waf.py` (linhas 27–29)

A função `inspect()` executa um loop de 1000 iterações (`x += i * i`) antes de inspecionar cada payload. O resultado nunca é usado.

**Impacto:** consome CPU real do processo WAF a cada mensagem — afeta diretamente as métricas de CPU do WAF medidas nos benchmarks. Não é overhead do coletor, é overhead artificial do próprio WAF.

**Decisão pendente:**

- **Remover** — WAF mais leve; resultados refletem apenas o overhead dos coletores (mais limpo para o TCC)

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
| 100.000   | 30   | 43s          | ~35s         | ~80s      | ~2h                         | A executar |
| 500.000   | 30   | 157s         | ~35s         | ~192s     | ~5h                         | A executar |
| 1.000.000 | 30   | 300s         | ~35s         | ~335s     | ~8h30                       | A executar |

> DURATION = `NUM_MESSAGES / 3500 + 15` (divisão inteira bash). Overhead inclui `docker compose down + build cacheado + up + shutdown`. Primeiro run de cada ferramenta tem build frio (~2-3 min extra).

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
