# TCC — Gerenciamento e Monitoramento de Rede (eBPF vs Clássicos)

Análise comparativa de desempenho entre três abordagens de monitoramento de rede aplicadas a uma VNF (Virtual Network Function):

1. **eBPF (BCC)**: coleta no nível do kernel via kprobes (`tcp_sendmsg`, `tcp_cleanup_rbuf`).
2. **sysstat**: polling em userspace via `/proc/net/dev`.
3. **Prometheus**: igual ao sysstat, com exposição adicional de métricas via HTTP (`:8000/metrics`).

O foco é medir o **overhead do monitoramento** (latência da coleta) ao monitorar um WAF simplificado rodando em Python.

---

## Arquitetura

```
Cliente TCP ──► WAF (porta 8080)
                      ▲
               observa via ferramenta
                      │
              Monitor-server (UDP :9999)
              eBPF | sysstat | Prometheus
              coleta bytes RX/TX + CPU/mem do WAF
                      ▲
               probe UDP (1/s)
               mede latência de roundtrip
                      │
              <ferramenta>_results.json
                      │
                 compare.py
                      │
         comparison.csv / comparison.json
```

- O **WAF** inspeciona cada payload e responde ao cliente. Não escreve métricas.
- O **monitor-server** coleta ativamente as métricas do WAF usando a ferramenta correspondente e serve qualquer request UDP com um JSON de métricas.
- O **probe** envia requests UDP a cada 1s e mede o tempo de roundtrip — essa latência é a métrica principal de comparação.
- A ferramenta muda entre os testes; o probe é o mesmo script (`probe.py`) nos três casos.

---

## Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── src/
│   ├── probe.py                  # Probe UDP único (configurado por variáveis de ambiente)
│   ├── vnf/
│   │   ├── waf.py                # WAF TCP (porta 8080) — SQLi, XSS, PathTraversal, RCE, NullByte
│   │   ├── monitor_ebpf.py       # Monitor eBPF: kprobes sport=8080 + psutil WAF
│   │   ├── monitor_sysstat.py    # Monitor sysstat: /proc/net/dev + psutil WAF
│   │   └── monitor_prometheus.py # Monitor Prometheus: /proc/net/dev + psutil WAF + HTTP :8000
│   ├── client/
│   │   ├── client.py             # Gerador de tráfego TCP → WAF
│   │   └── gen_payload.py        # Gerador do payload.bin
│   └── compare.py                # Consolida resultados em CSV e JSON (3 modos)
├── configs/
│   ├── Dockerfile                # Imagem base Ubuntu 24.04 + BCC
│   └── Dockerfile.client         # Imagem para o gerador de tráfego
├── scripts/
│   ├── run_ebpf.sh               # Executa o teste completo com eBPF
│   ├── run_sysstat.sh            # Executa o teste completo com sysstat
│   ├── run_prometheus.sh         # Executa o teste completo com Prometheus
│   └── run_multi.sh              # Executa N repetições sequenciais de uma ferramenta
├── docs/
│   └── arquitetura_c4.svg        # Diagrama de arquitetura C4
├── results/                      # Resultados gerados (*_<N>_run<ID>_results.json, .csv, .json)
├── docker-compose.ebpf.yml
├── docker-compose.sysstat.yml
└── docker-compose.prometheus.yml
```

---

## Como Rodar

### Requisitos
- Linux nativo (kernel 6.10+, testado no 6.12).
- Docker + Docker Compose.
- Headers do kernel instalados no host (necessário para o monitor eBPF).

### Executar cada teste

Cada script sobe a stack completa (WAF + monitor-server + cliente + probe), aguarda a coleta e exibe um resumo:

```bash
bash scripts/run_ebpf.sh
bash scripts/run_sysstat.sh
bash scripts/run_prometheus.sh
```

Variáveis de ambiente opcionais:
```bash
NUM_MESSAGES=1000 bash scripts/run_ebpf.sh        # 1000 mensagens
NUM_MESSAGES=1000 RUN_ID=2 bash scripts/run_ebpf.sh  # run específico
```

### Executar múltiplas repetições

```bash
bash scripts/run_multi.sh <ferramenta> <num_messages> <num_runs>

bash scripts/run_multi.sh ebpf       100 5
bash scripts/run_multi.sh sysstat    100 5
bash scripts/run_multi.sh prometheus 100 5
```

Salva cada repetição como `<ferramenta>_<N>_run<ID>_results.json` e gera a agregação ao final.

### Gerar comparativo

```bash
python3 src/compare.py 100        # compara 3 ferramentas para N=100 (run 1)
python3 src/compare.py 100 5      # agrega 5 runs de N=100 (média ± desvio)
python3 src/compare.py            # cross-N com todos os valores disponíveis
```

---

## Métricas Coletadas

| Métrica | Origem | Descrição |
|---------|--------|-----------|
| `monitor_latency_avg_ms` | probe | Latência média da roundtrip UDP (overhead do monitoramento) |
| `monitor_latency_stddev_ms` | probe | Desvio padrão da latência |
| `bytes_rx / bytes_tx` | monitor-server | eBPF: kprobe sport=8080; sysstat/Prom: `/proc/net/dev` |
| `cpu_avg_pct` | monitor-server (psutil) | Uso médio de CPU do processo WAF |
| `mem_avg_mb` | monitor-server (psutil) | Uso médio de memória do processo WAF |

---

## Detalhes dos Monitores

### eBPF (`monitor_ebpf.py`)
- Carrega programa BPF via BCC.
- `kprobe__tcp_sendmsg`: acumula bytes TX quando `sport == 8080` (respostas do WAF).
- `kprobe__tcp_cleanup_rbuf`: acumula bytes RX quando `sport == 8080` (requisições recebidas pelo WAF).
- Filtro `sport=8080` evita dupla contagem no loopback.
- Requer `privileged: true`, `pid: host`, `/sys/kernel/debug`, headers do kernel.

### sysstat (`monitor_sysstat.py`)
- Lê `/proc/net/dev` (interface `lo`) a cada request UDP recebido.
- Retorna delta de bytes RX/TX em relação ao início do teste.
- Requer `pid: host`.

### Prometheus (`monitor_prometheus.py`)
- Mesma lógica de coleta do sysstat.
- Expõe Gauges em `:8000/metrics` via `prometheus_client`.
- Requer `pid: host`.

---

## Resultados

### N = 100 mensagens (run 1)

| Métrica | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| Latência média (ms) | 0.4347 | 0.4510 | **0.3779** |
| Desvio padrão (ms) | **0.0290** | 0.0603 | 0.0923 |
| Latência máx (ms) | **0.4772** | 0.6338 | 0.6418 |
| Latência mín (ms) | 0.2854 | 0.2464 | **0.2261** |
| Amostras coletadas | **100** | **100** | **100** |
| CPU média WAF (%) | 0.05 | **0.04** | 0.05 |
| Memória média WAF (MB) | **11.29** | 11.37 | 11.47 |
| Bytes RX | 89 338 | 160 987 | 159 173 |
| Bytes TX | 1 202 | 160 987 | 159 173 |
| Duração (s) | 100.08 | 100.08 | 100.07 |

### N = 1000 mensagens (run 1)

| Métrica | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| Latência média (ms) | **0.4071** | 0.4531 | 0.4760 |
| Desvio padrão (ms) | 0.0833 | 0.1221 | **0.0401** |
| Latência máx (ms) | **1.2971** | 2.9097 | 0.8506 |
| Latência mín (ms) | **0.1840** | 0.2120 | 0.2587 |
| Amostras coletadas | 999 | 999 | 999 |
| CPU média WAF (%) | **0.05** | **0.05** | **0.05** |
| Memória média WAF (MB) | 11.50 | **11.49** | **11.49** |
| Bytes RX | 868 696 | 1 794 483 | 1 593 103 |
| Bytes TX | 12 325 | 1 794 483 | 1 593 103 |
| Duração (s) | 1000.14 | 1000.19 | 1000.22 |
