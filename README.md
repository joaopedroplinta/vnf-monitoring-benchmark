<h1 align="center">vnf-monitoring-benchmark</h1>

<p align="center">
  <b>Quanto custa monitorar uma função de rede virtualizada?</b><br>
  Comparação de desempenho entre <b>eBPF</b>, <b>Sysstat</b>, <b>Prometheus</b> e <b>API do Docker</b> aplicados a um WAF.
</p>

<p align="center">
  <img alt="Licença MIT" src="https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg">
  <img alt="Linux kernel 6.10+" src="https://img.shields.io/badge/Linux-kernel%206.10%2B-informational">
  <img alt="eBPF libbpf + CO-RE" src="https://img.shields.io/badge/eBPF-libbpf%20%2B%20CO--RE-orange">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB">
  <img alt="Docker Compose" src="https://img.shields.io/badge/Docker-Compose-2496ED">
</p>

<p align="center">
  <a href="#como-funciona">Como funciona</a> ·
  <a href="#início-rápido">Início rápido</a> ·
  <a href="#estrutura-do-repositório">Estrutura</a> ·
  <a href="#resultados">Resultados</a> ·
  <a href="https://vnf-lab.up.railway.app">Dashboard online</a> ·
  <a href="#limitações">Limitações</a> ·
  <a href="#sobre-o-trabalho">Sobre o trabalho</a>
</p>

---

Benchmark reprodutível que mede o **overhead de quatro abordagens de monitoramento** enquanto um WAF simplificado processa carga:

| Abordagem | Como coleta |
|---|---|
| **eBPF** (libbpf + CO-RE) | kprobes no kernel (`tcp_sendmsg`, `tcp_cleanup_rbuf`), sem BCC/LLVM em runtime |
| **Sysstat** | leitura em espaço de usuário de `/proc/net/dev` |
| **Prometheus** | igual ao Sysstat, com um endpoint HTTP `/metrics` ativo |
| **Docker** | `container.stats()` da API do Docker (cgroups) pelo SDK Python, via `/var/run/docker.sock` |

A métrica principal é o **tempo de resposta do observador**: o RTT de um probe UDP mostra quanto tempo cada ferramenta leva para entregar suas métricas. CPU e memória do WAF e do observador são métricas secundárias.

## Como funciona

<p align="center">
  <img src="docs/imagens/C4model.drawio.svg" width="720" alt="Diagrama de contêineres (C4, Nível 2) da topologia experimental">
</p>

- O **cliente** envia payloads pré-gerados (60% benignos, 40% maliciosos) ao **WAF** por conexões TCP persistentes.
- O **WAF** inspeciona cada payload (SQLi, XSS, Path Traversal, RCE, Null Byte) com `asyncio` + `ThreadPoolExecutor` e responde ao cliente `ALLOWED` ou `BLOCKED`.
- O **observador** coleta métricas do WAF com a ferramenta em teste e responde a requisições UDP com um JSON.
- O **probe** envia uma requisição UDP por segundo e mede o RTT. O mesmo script é usado nas quatro ferramentas.

> [!NOTE]
> O RTT mede o tempo que o *observador* leva para responder. O impacto sobre o *WAF* é avaliado pela CPU e pela memória do WAF.

## Início rápido

Requer Linux nativo com BTF (`/sys/kernel/btf/vmlinux`), Docker Compose e Python 3.10+.

```bash
git clone https://github.com/joaopedroplinta/vnf-monitoring-benchmark.git
cd vnf-monitoring-benchmark
pip install matplotlib numpy

python3 scripts/gen_payloads.py 100000            # gera os payloads (uma vez)
NUM_MESSAGES=100000 bash scripts/run_ebpf.sh
NUM_MESSAGES=100000 bash scripts/run_sysstat.sh
NUM_MESSAGES=100000 bash scripts/run_prometheus.sh
NUM_MESSAGES=100000 bash scripts/run_docker.sh
python3 src/compare.py 100000                     # compara as quatro ferramentas
```

A bateria completa (30 execuções por ferramenta e volume, ~14 h) e as variáveis de ambiente estão em **[docs/reproducao.md](docs/reproducao.md)**.

## Estrutura do repositório

| Pasta | Conteúdo |
|---|---|
| [`src/`](src) | WAF, observadores (eBPF, Sysstat, Prometheus, Docker), cliente, probe e comparador |
| [`scripts/`](scripts) | geração de payloads, execução dos testes e gráficos |
| [`configs/`](configs) | Dockerfiles |
| [`dashboard/`](dashboard) | dashboard interativo (React + TypeScript) com os resultados das 960 execuções (duas baterias de 480) |
| [`results/`](results) | resultados brutos (JSON) e agregados (CSV/JSON) das execuções |
| [`docs/`](docs) | tese em LaTeX, diagrama C4, apresentações e documentação detalhada |

## Dashboard

**Acesse online: [https://vnf-lab.up.railway.app](https://vnf-lab.up.railway.app)**

Os resultados podem ser explorados em um dashboard interativo (React, TypeScript, Tailwind CSS e Plotly), com navegação por seis abas, filtros por bateria, ferramenta e volume, IC95%, execuções individuais, download dos dados e modo claro/escuro. É uma página estática: os dados vêm de `dashboard/data.csv` e `dashboard/data_otimizada.csv`.

```bash
cd dashboard
npm install        # precisa de Node 22 ou mais recente
npm run dev
```

Para rodar localmente, abra `http://localhost:5173`. Testes, geração dos dados e instruções de hospedagem na Railway em **[dashboard/README.md](dashboard/README.md)**.

Documentação detalhada:
[Reprodução](docs/reproducao.md) ·
[Resultados](docs/resultados.md) ·
[Métricas e observadores](docs/metricas-e-observadores.md) ·
[Arquitetura](docs/architecture.md) ·
[Diário do projeto](relatorio_projeto.md)

## Resultados

960 execuções em duas baterias, ambas com média ± IC95% (t de Student, 30 repetições por combinação), no kernel 7.0.0-38 em modo texto:

- **Coleta oficial:** 480 execuções (4 ferramentas × 4 volumes × 30), com WAF e cliente em 1 processo (recoleta com o WAF corrigido; a primeira coleta está arquivada em `results/arquivo_primeira_coleta/`).
- **Coleta complementar:** mais 480 execuções, com WAF e cliente em 4 processos e leitura direta, em que o WAF inspeciona 100% de N.

**Tempo de resposta médio do observador na coleta oficial (ms, menor é melhor):**

| Volume de mensagens | eBPF | Sysstat | Prometheus | Docker |
|---|:---:|:---:|:---:|:---:|
| 100.000 | **0,533** | 0,614 | 0,622 | 2,579 |
| 500.000 | **0,496** | 0,571 | 0,583 | 2,503 |
| 1.000.000 | **0,498** | 0,575 | 0,585 | 2,498 |
| 2.000.000 | **0,500** | 0,572 | 0,584 | 2,506 |

- O **eBPF teve o menor tempo de resposta nos quatro volumes**, com IC95 sem sobreposição. A vantagem é de 13% a 15% sobre Sysstat e Prometheus e de ~80% sobre o Docker, cujo RTT (~2,5 ms) inclui a consulta ao daemon.
- **Memória do observador:** Sysstat ~14 MB, eBPF ~15 MB, Prometheus ~25 MB (o custo do servidor HTTP), Docker ~31 MB.
- **CPU do WAF** equivalente entre as ferramentas. **CPU do observador** inconclusiva: em 13 dos 16 grupos o IC95% é maior ou igual a 50% da média.
- **Coleta complementar (100% de N inspecionado):** a ordem se mantém (eBPF ~0,90 ms, Sysstat ~1,01, Prometheus ~1,04 e Docker ~2,65). O aumento de ~0,4 ms nos três primeiros vem do `psutil` consultar 4 processos do WAF por sonda, e o Docker faz uma única chamada.

<p align="center">
  <img src="results/plots/tempo_resposta_por_n.png" width="560" alt="Tempo de resposta médio do observador por volume de mensagens">
</p>

Tabelas completas por volume, gráficos e observações: **[docs/resultados.md](docs/resultados.md)**.

## Limitações

- **Loopback:** o tráfego passa pela interface `lo`, sem o overhead de drivers de NIC físico; valores absolutos seriam diferentes em rede real.
- **Recursos compartilhados:** cliente, WAF e observador dividem kernel e núcleos de CPU.
- **WAF simplificado:** implementação em Python, idêntica em todos os experimentos, então as diferenças refletem o custo de cada ferramenta. Não há servidor de aplicação atrás dele: o WAF só classifica e responde.
- **Ambiente único:** os testes rodaram em uma máquina, sem ambiente de produção; o volume de pacotes de produção seria maior.
- **Volume nominal:** na coleta oficial, para N ≥ 500k o WAF processa só 62% a 88% de N (a janela supõe 15 mil msg/s e o ambiente sustentou 7 a 8 mil); a coleta complementar elimina esse limite e preserva a ordem. Veja [resultados](docs/resultados.md#n-nominal--mensagens-processadas).
- **Lotes não intercalados:** cada combinação ferramenta × volume foi coletada em sequência, o que mistura a ferramenta com o estado da máquina naquele momento.
- **Docker:** memória e CPU do WAF vêm do cgroup, não do processo, e não são comparáveis às das demais ferramentas; o socket do Docker exige privilégio.
- **Prometheus sem scraping:** é avaliado só como exporter; nenhum servidor consulta o endpoint durante os testes.

## Sobre o trabalho

Trabalho de Conclusão de Curso do Bacharelado em Ciência da Computação, IFPR Campus Pinhais (2026).

> **Monitoramento de Funções Virtualizadas de Redes: um estudo comparativo entre ferramentas de extração de comportamento**

| | |
|---|---|
| **Autores** | João Pedro dos Santos Henrique Plinta · Rafael Correia Alves |
| **Orientador** | Prof. Guilherme Werneck de Oliveira |

O texto da tese está em [`docs/`](docs) (LaTeX) e é compilado no Overleaf: o `docs/main.tex` referencia `capítulos/` com nomes acentuados e os logotipos não estão versionados, então a pasta não compila sozinha. O artigo no modelo IEEE Access está em [`docs/ieee/`](docs/ieee) e compila com `docs/ieee/compilar.sh` (pdfLaTeX, também no CI). Slides (21), PDF e roteiros estão em [`docs/apresentacao/`](docs/apresentacao).

## Licença

[MIT](LICENSE) © 2026 João Pedro dos Santos Henrique Plinta e Rafael Correia Alves.
