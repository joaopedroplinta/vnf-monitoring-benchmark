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
│   └── compare.py                # Consolida resultados em CSV e JSON
├── configs/
│   ├── Dockerfile                # Imagem base Ubuntu 24.04 + BCC
│   └── Dockerfile.client         # Imagem para o gerador de tráfego
├── scripts/
│   ├── run_ebpf.sh               # Executa o teste completo com eBPF
│   ├── run_sysstat.sh            # Executa o teste completo com sysstat
│   └── run_prometheus.sh         # Executa o teste completo com Prometheus
├── results/                      # Resultados gerados (.csv, .json)
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

Ou manualmente:
```bash
docker compose -f docker-compose.ebpf.yml up --build -d
docker compose -f docker-compose.ebpf.yml logs -f ebpf-collector
```

### Gerar comparativo

Após rodar os três testes:
```bash
python3 src/compare.py
```

Gera `results/comparison.csv` e `results/comparison.json`.

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

## Resultados (última execução — 60s, 60 amostras)

> ⚠️ Resultados obtidos com a arquitetura anterior (WAF escrevia métricas). Serão atualizados após nova execução.

| Métrica | eBPF | sysstat | Prometheus |
|---------|------|---------|------------|
| Latência média (ms) | 0.301 | 0.332 | 0.308 |
| Desvio padrão (ms) | 0.089 | 0.039 | 0.107 |
| Latência máx (ms) | 0.855 | 0.475 | 0.918 |
| Latência mín (ms) | 0.168 | 0.231 | 0.191 |
| CPU média WAF (%) | 0.33 | 0.33 | 0.83 |
| Memória média WAF (MB) | 15.07 | 15.20 | 15.43 |
| Bytes RX | ~123 MB | ~122 MB | ~122 MB |
