# Reprodução dos experimentos

Guia completo para reproduzir a bateria de 360 execuções. Para uma execução rápida, veja o [início rápido](../README.md#início-rápido).

## Ambiente

**Máquina usada nos resultados oficiais:**

| Item | Especificação |
|------|---------------|
| CPU | AMD Ryzen 5 5500 (6 núcleos / 12 threads, até 4,27 GHz, L3 16 MB) |
| RAM | 16 GB |
| SO | Ubuntu 26.04 LTS (Resolute Raccoon) |
| Kernel | 7.0.0-15-generic |

**Requisitos mínimos:**

- Linux nativo (kernel 6.10+, testado no 7.0)
- Docker + Docker Compose
- Python 3.10+
- BTF habilitado no kernel (`/sys/kernel/btf/vmlinux`, presente em kernels 5.8+)

**Bibliotecas Python do host** (os contêineres instalam as suas próprias via Dockerfile):

```bash
pip install matplotlib numpy          # geração de gráficos (plot_results.py)
```

> `psutil` e `prometheus_client` são instalados apenas dentro dos contêineres.

## Passo 1 — Gerar os payloads (uma vez)

Os payloads são pré-gerados no host e montados no contêiner do cliente. Os arquivos não são versionados (`data/payloads/` está no `.gitignore`).

```bash
python3 scripts/gen_payloads.py 100000   # → data/payloads/payloads_100000_6040.bin
python3 scripts/gen_payloads.py 500000   # → data/payloads/payloads_500000_6040.bin
python3 scripts/gen_payloads.py 1000000  # → data/payloads/payloads_1000000_6040.bin
python3 scripts/gen_payloads.py 2000000  # → data/payloads/payloads_2000000_6040.bin
```

Opções do gerador:

```bash
python3 scripts/gen_payloads.py <count> [--ratio 60] [--seed 42] [--out FILE]
# --ratio: percentual de mensagens limpas (padrão: 60 → 60% limpos / 40% maliciosos)
# --seed:  semente aleatória para reprodutibilidade (padrão: 42)
```

## Passo 2 — Executar um teste

Cada script sobe a stack completa (WAF + observador + cliente + probe), aguarda o probe finalizar via `docker wait` e exibe um resumo:

```bash
NUM_MESSAGES=100000 bash scripts/run_ebpf.sh
NUM_MESSAGES=100000 bash scripts/run_sysstat.sh
NUM_MESSAGES=100000 bash scripts/run_prometheus.sh
```

O script deriva o arquivo de payloads a partir de `NUM_MESSAGES`. Se o arquivo não existir, aborta com a instrução de geração.

### Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `NUM_MESSAGES` | 100000 | Volume nominal — usado para `DURATION` e para a nomenclatura dos resultados |
| `DURATION` | `NUM_MESSAGES/15000 + 20` | Duração da coleta (segundos) |
| `RUN_ID` | 1 | Identificador da execução |
| `WORKERS` | 200 | Conexões assíncronas do cliente (corrotinas asyncio) |
| `PAYLOADS_FILE_HOST` | `data/payloads/payloads_<N>_6040.bin` | Caminho do arquivo de payloads no host (sobrescreve o padrão) |

> [!WARNING]
> A execução termina quando `DURATION` acaba, e o divisor 15.000 é maior que a vazão real medida (~7,5 mil msg/s). Por isso, para N ≥ 500k o WAF processa só parte de N. Veja a tabela em [resultados](resultados.md#n-nominal--mensagens-processadas).

## Passo 3 — Múltiplas repetições

```bash
bash scripts/run_multi.sh <ferramenta> <num_messages> <num_runs> [--pre]

# Exemplos:
bash scripts/run_multi.sh ebpf       100000 5
bash scripts/run_multi.sh sysstat    100000 5
bash scripts/run_multi.sh prometheus 100000 5

# Com a flag --pre: salva em results/pre_testes/ (testes preliminares)
bash scripts/run_multi.sh prometheus 100000 5 --pre
```

Cada repetição é salva como `<ferramenta>_<N>_run<ID>_results.json`, e a agregação é gerada ao final.

## Gerar o comparativo

```bash
python3 src/compare.py 100000        # compara as 3 ferramentas para N=100000 (run 1)
python3 src/compare.py 100000 5      # agrega 5 runs de N=100000 (média ± IC95%)
python3 src/compare.py               # cross-N com todos os valores disponíveis
```

Para gerar os gráficos: `python3 scripts/plot_results.py` (saída em `results/plots/`).

## Tempo de execução

Tempo medido nos resultados oficiais para um lote de 30 execuções de **uma** ferramenta, incluindo o overhead do Docker:

| N | Por execução | Lote de 30 |
|---|---|---|
| 100.000 | ~0,6 min | ~19 min |
| 500.000 | ~1,2 min | ~37 min |
| 1.000.000 | ~1,8 min | ~54 min |
| 2.000.000 | ~2,9 min | ~87 min |

A bateria completa (3 ferramentas × 4 volumes × 30 execuções) leva cerca de **10 horas** de execução contínua.
