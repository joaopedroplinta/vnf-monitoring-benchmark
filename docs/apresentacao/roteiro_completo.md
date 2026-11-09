# ROTEIRO COMPLETO — para dominar o conteúdo (Defesa Final do TCC)

**Título:** Monitoramento de Funções Virtualizadas de Redes: um estudo comparativo entre ferramentas de extração de comportamento
**Duração-alvo:** ~20 min de fala (20 slides) + arguição da banca.

Cada tópico tem três partes:
- 🎯 **Objetivo do slide** — o que a banca precisa entender ao sair dele.
- 🗣️ **O que dizer** — a fala (não decore palavra por palavra; entenda a lógica e fale com naturalidade).
- ↪️ **Transição** — a ponte para o próximo slide.

> Regra de ouro: olhe para a banca, não leia o slide. O slide é apoio visual; você é a explicação.

---

## SLIDE 1 — Capa · ~0:45

🎯 **Objetivo:** apresentar você, o Rafael, o orientador e resumir o TCC em uma frase direta.

🗣️ **O que dizer:**
> "Bom dia / Boa tarde a todos. Eu sou o João Pedro, e junto com o Rafael, sob orientação do professor Guilherme Werneck, vamos apresentar a defesa final do nosso TCC. Em uma frase: nós comparamos quatro abordagens de monitoramento aplicadas a uma função de rede virtualizada — eBPF, Sysstat, Prometheus e a API do Docker — para medir qual delas impõe a menor sobrecarga ao ambiente monitorado."

↪️ **Transição:** "Antes de entrar nos dados, deixem eu mostrar o roteiro que vamos percorrer."

---

## SLIDE 2 — Roteiro da apresentação · ~0:45

🎯 **Objetivo:** dar à banca o mapa dos 8 blocos e plantar a pergunta central.

🗣️ **O que dizer:**
> "A apresentação está organizada em oito partes: o contexto de NFV; o problema, a hipótese e os objetivos; as quatro abordagens avaliadas; a lacuna na literatura; a metodologia e a arquitetura experimental; os resultados das 480 execuções oficiais; a análise de sensibilidade da vazão com mais 480 execuções; e por fim a síntese, as conclusões e os trabalhos futuros."
> "E tudo gira em torno de uma pergunta central: **monitorar uma VNF tem um custo computacional — qual ferramenta cobra menos por isso?**"

↪️ **Transição:** "Vamos começar pelo contexto: por que monitorar funções virtualizadas é tão sensível?"

---

## SLIDE 3 — Contexto: Virtualização de Funções de Rede (NFV) · ~1:15

🎯 **Objetivo:** explicar NFV/VNF e destacar que o monitor roda co-localizado à VNF, disputando CPU e RAM e impactando o tempo de tomada de decisão do orquestrador.

🗣️ **O que dizer:**
> "A Virtualização de Funções de Rede, ou NFV, desacopla os serviços de rede de equipamentos proprietários e passa a executá-los como software — as VNFs — em servidores comuns. Exemplos clássicos são firewalls, detectores de intrusão, balanceadores de carga e, no nosso caso, um WAF, um Firewall de Aplicação Web."
> "Para que essa flexibilidade funcione em ambientes de redes vivas, onde a demanda varia o tempo todo, o bloco de gerência e orquestração — o MANO — precisa monitorar continuamente CPU, memória, vazão e latência para decidir quando escalar ou recuperar uma VNF."
> "E aqui está o ponto-chave: **o observador não é um elemento externo à infraestrutura; ele roda co-localizado à VNF no mesmo host, disputando os mesmos núcleos de CPU e a mesma memória.** Se o coletor for pesado ou lento, ele degrada justamente o serviço que deveria apenas observar e atrasa a tomada de decisão do orquestrador."

↪️ **Transição:** "É exatamente daí que emergem o nosso problema de pesquisa e a nossa hipótese."

---

## SLIDE 4 — Problema de pesquisa, hipótese e lacuna · ~1:15

🎯 **Objetivo:** apresentar a questão de pesquisa com as 4 ferramentas, a hipótese (kernel vs. espaço de usuário) e a lacuna empírica na literatura.

🗣️ **O que dizer:**
> "Diante desse impacto no gerenciamento e na tomada de decisão, nossa questão de pesquisa é: **quais são as diferenças práticas de desempenho entre o eBPF, o Sysstat, o Prometheus e a API do Docker no monitoramento de uma VNF, e qual oferece menor sobrecarga sem comprometer a qualidade da coleta?**"
> "Nossa hipótese é que o **eBPF**, por operar no nível do *kernel* via *kprobes*, apresenta menor tempo de resposta e menor sobrecarga frente às três abordagens que operam em espaço de usuário: o Sysstat e o Prometheus, que fazem *polling* lendo e parseando arquivos do `/proc`, e a API do Docker, que consulta os *cgroups* sob demanda por meio do *daemon* `dockerd`."
> "E a lacuna que atacamos na literatura é que, embora essas tecnologias sejam muito usadas e estudadas isoladamente, faltam comparações empíricas controladas avaliando as quatro simultaneamente sobre uma mesma VNF e com aumento progressivo de carga."

↪️ **Transição:** "Com o problema e a hipótese definidos, estes foram os nossos objetivos."

---

## SLIDE 5 — Objetivos · ~0:45

🎯 **Objetivo:** mostrar metas claras e verificáveis que foram integralmente cumpridas na versão final do trabalho.

🗣️ **O que dizer:**
> "O objetivo geral foi compreender como eBPF, Sysstat, Prometheus e a API do Docker influenciam o tempo de resposta de extração de métricas e a sobrecarga no monitoramento de uma VNF sob diferentes condições de consumo."
> "E nos objetivos específicos: analisamos a literatura de monitoramento em NFV; implementamos os quatro coletores para monitorar um WAF; executamos experimentos quantitativos em quatro volumes de carga — de 100 mil a 2 milhões de mensagens — medindo tempo de resposta, CPU e memória; e analisamos as vantagens, limitações e *trade-offs* de cada abordagem."

↪️ **Transição:** "Vamos entender agora como cada uma das quatro abordagens coleta os dados na prática."

---

## SLIDE 6 — As quatro abordagens comparadas · ~1:45

🎯 **Objetivo:** explicar com clareza a diferença mecânica entre ler no kernel (eBPF), fazer parsing de `/proc` (Sysstat/Prometheus) e passar pelo daemon para ler cgroups (Docker). Esse slide explica todos os resultados.

🗣️ **O que dizer:**
> "Temos aqui as quatro arquiteturas de coleta:"
> "1. O **eBPF** opera no nível do *kernel* usando `libbpf` com CO-RE, sem precisar do BCC ou do LLVM em tempo de execução. Anexamos *kprobes* nas funções `tcp_sendmsg` e `tcp_cleanup_rbuf` filtrando a porta 8080 do WAF. O programa BPF soma os bytes direto em um mapa `ARRAY` no kernel, e o observador em espaço de usuário só lê esse valor já acumulado."
> "2. O **Sysstat** representa o *polling* clássico em espaço de usuário: a cada sonda, ele abre e faz o *parsing* textual de `/proc/net/dev` e consulta o `psutil`, que lê `/proc/<pid>` para obter CPU e memória do WAF."
> "3. O **Prometheus** executa exatamente a mesma coleta do Sysstat, mas mantém um servidor HTTP ativo na porta 8000 expondo as métricas em `/metrics`. Aqui avaliamos o custo do *exporter* em execução."
> "4. E a **API do Docker**, incluída para avaliar a coleta nativa de contêineres: o observador usa o SDK Python do Docker para chamar `stats(one_shot=True)` via socket Unix (`/var/run/docker.sock`). Quem lê os arquivos dos *cgroups* v2 do kernel é o *daemon* `dockerd`, que monta um JSON completo e devolve ao observador."
> "Guarde esse contraste central: **ler um mapa pronto no kernel vs. parsear `/proc` no espaço de usuário vs. fazer IPC até o daemon do Docker para ler cgroups.**"

↪️ **Transição:** "Mas o que a literatura já havia medido sobre isso?"

---

## SLIDE 7 — Trabalhos relacionados e lacuna na literatura · ~1:00

🎯 **Objetivo:** situar o trabalho frente aos artigos da Tabela 1 do TCC (incluindo os estudos de Docker/cgroups e de NFV).

🗣️ **O que dizer:**
> "Na revisão da literatura, encontramos estudos que cobrem partes desse problema: Cassagnes et al. (2020) comparam eBPF com *polling*, mas sem Prometheus ou API do Docker; Casalicchio (2017) e Wiedner et al. (2023) investigam o desempenho do Docker e a latência dos *cgroups* v1 e v2; Dinga et al. (2023) avaliam o Prometheus e outras ferramentas em microsserviços Docker, mas sem eBPF; Kannan (2024) e Shahinfar (2025) focam apenas no eBPF; e Oliveira et al. (2026) avaliam o impacto da latência do Sysstat na orquestração MANO."
> "Como destaca a última linha da tabela, **o nosso trabalho é o primeiro benchmark controlado a comparar diretamente as quatro abordagens juntas — eBPF, Sysstat, Prometheus e API do Docker — sobre uma mesma VNF isolada sob cargas crescentes.**"

↪️ **Transição:** "Vou mostrar agora a metodologia e o ambiente que construímos para fazer essa comparação de forma justa."

---

## SLIDE 8 — Metodologia e ambiente experimental · ~1:00

🎯 **Objetivo:** justificar a escolha do WAF e apresentar o hardware/software padronizado (modo texto, Kernel 7.0.0-38, versões fixadas).

🗣️ **O que dizer:**
> "Esta é uma pesquisa aplicada, quantitativa, comparativa e experimental."
> "Como VNF representativa, implementamos um WAF em Python com `asyncio` e `ThreadPoolExecutor` que inspeciona cinco classes de ataque: SQLi, XSS, Path Traversal, RCE e Null Byte. Escolhemos um WAF justamente porque a inspeção de conteúdo é intensiva em CPU: qualquer sobrecarga adicional do coletor concorre diretamente com a VNF e se torna mensurável."
> "Todos os testes finais rodaram em uma máquina física dedicada com Ryzen 5 5500, 16 GB de RAM, Ubuntu 26.04 operando em **modo texto** (`multi-user.target`, sem interface gráfica para eliminar ruído), Kernel Linux 7.0.0-38 e Docker Engine 29.8.2, com quatro pilhas Docker Compose independentes e versões de bibliotecas fixadas."

↪️ **Transição:** "No próximo slide temos o diagrama C4 dessa topologia."

---

## SLIDE 9 — Arquitetura experimental (Diagrama C4 — Nível 2) · ~1:00

🎯 **Objetivo:** explicar o fluxo entre Cliente, WAF, Observador e Coletor (`probe.py`).

🗣️ **O que dizer:**
> "A topologia tem quatro componentes:"
> "1. O **Cliente** abre 200 corrotinas assíncronas com conexões TCP persistentes para a porta 8080 do WAF, enviando mensagens com prefixo de 4 bytes."
> "2. O **WAF** inspeciona cada carga, responde `ALLOWED` ou `BLOCKED`, e a cada 100 requisições persiste as estatísticas de inspeção em `waf_metrics.json` usando gravação atômica."
> "3. O **Observador** é o contêiner que muda entre as quatro pilhas — eBPF, Sysstat, Prometheus ou Docker. Ele escuta na porta UDP 9999."
> "4. E o **Coletor (`probe.py`)** é o nosso instrumento de medição: ele envia uma requisição UDP por segundo ao observador e mede o tempo de ida e volta com resolução de nanossegundos (`time.time_ns()`). **Esse RTT UDP é a nossa métrica primária**, pois mede diretamente quanto tempo cada ferramenta leva para coletar e entregar as métricas."

↪️ **Transição:** "E como garantimos a validade estatística das medições?"

---

## SLIDE 10 — Protocolo de testes e rigor estatístico · ~1:15

🎯 **Objetivo:** destacar o determinismo da carga (`seed=42`), as 480 execuções oficiais, a correção atômica e o IC95%.

🗣️ **O que dizer:**
> "Avaliamos quatro volumes nominais de mensagens: 100 mil, 500 mil, 1 milhão e 2 milhões. Os arquivos de carga têm 60% de mensagens benignas e 40% maliciosas, embaralhadas com semente fixa `42` — garantindo que as quatro ferramentas enfrentem exatamente a mesma sequência de requisições."
> "Para cada uma das 16 combinações de ferramenta e volume, executamos **30 repetições independentes**, totalizando **480 execuções oficiais** (com zero falhas de leitura após a gravação atômica do `waf_metrics.json`)."
> "A métrica primária é o RTT UDP do observador; as secundárias são CPU e memória do observador e do WAF; e usamos o tempo médio de inspeção (`~0,080 ms`) e os bytes RX/TX como métricas de validação. Tudo foi agregado pela média com **intervalo de confiança de 95% via distribuição t de Student** ($n=30$), e também disponibilizado no nosso painel interativo online."

↪️ **Transição:** "Vamos então aos resultados das 480 execuções, começando pela métrica primária."

---

## SLIDE 11 — Tempo de resposta do observador (RTT UDP) ⭐ · ~1:45

🎯 **Objetivo:** apresentar o resultado principal do TCC com clareza absoluta.

🗣️ **O que dizer:**
> "Aqui temos o resultado central do trabalho: o tempo de resposta médio do observador nos quatro volumes."
> "O **eBPF obteve o menor tempo de resposta em todos os volumes** — cerca de `0,50 ms` a partir de 500 mil mensagens. Isso representa uma redução de **12,8% a 13,4% em relação ao Sysstat** (`~0,57 ms`), de **14,4% a 14,9% em relação ao Prometheus** (`~0,58 ms`), e de **cerca de 80% — cinco vezes menor — em relação à API do Docker** (`~2,50 ms`)."
> "Em nenhum volume os intervalos de confiança de 95% do eBPF se sobrepõem aos das demais ferramentas, comprovando que a diferença é estatisticamente significativa."
> "Isso confirma na prática a diferença arquitetural: o eBPF lê contadores já prontos em memória compartilhada com o kernel, enquanto Sysstat e Prometheus fazem *parsing* de `/proc/net/dev` e `psutil` a cada requisição, e o Prometheus ainda adiciona de 1,4% a 2,1% sobre o Sysstat pelo servidor HTTP ativo."

↪️ **Transição:** "Mas como se comportam a dispersão entre as 30 execuções e por que o Docker levou 2,5 ms? É o que vemos no próximo slide."

---

## SLIDE 12 — Distribuição do RTT e o custo da API do Docker · ~1:15

🎯 **Objetivo:** mostrar os boxplots (com e sem Docker) e explicar a análise isolada das etapas do Docker (`bench_docker_cgroup.py`).

🗣️ **O que dizer:**
> "No gráfico à esquerda temos os boxplots das 30 execuções. Na linha superior estão as quatro ferramentas; como os `2,5 ms` do Docker comprimem a escala, a linha inferior faz um zoom omitindo o Docker. Vemos que a caixa do eBPF fica inteiramente abaixo de Sysstat e Prometheus em todos os volumes, e que todas as ferramentas tiveram baixíssima dispersão entre execuções — desvio-padrão de apenas 1% a 2% da média."
> "E por que o Docker leva cerca de `2,5 ms`? Porque cada sonda UDP dispara uma cadeia síncrona: o SDK Python envia uma requisição HTTP pelo socket Unix, o *daemon* `dockerd` lê os arquivos do *cgroup*, serializa toda a árvore de estatísticas do contêiner em JSON e devolve ao Python."
> "Para comprovar isso, fizemos uma análise isolada das etapas (`bench_docker_cgroup.py`): **ler os arquivos do cgroup diretamente no sistema de arquivos leva apenas `0,04 a 0,05 ms`**; um ping vazio ao daemon já custa `0,5 a 0,6 ms`; e a chamada `stats(one_shot=True)` leva de `1,4 a 1,7 ms` — cerca de 30 vezes mais que a leitura direta. Ou seja, o kernel entrega o dado rápido; o custo está na camada de IPC e serialização do daemon."

↪️ **Transição:** "Visto o tempo de resposta, vamos avaliar o impacto sobre a VNF: o consumo de CPU do WAF."

---

## SLIDE 13 — Consumo de CPU do processo WAF (Controle) · ~0:50

🎯 **Objetivo:** mostrar que o WAF satura de forma igual nos 4 coletores (~104–110%) e que nenhum coletor interfere na VNF.

🗣️ **O que dizer:**
> "O consumo de CPU do WAF atua como variável de controle. A partir de 500 mil mensagens, o WAF opera em saturação entre `104% e 110%` de um núcleo lógico nos quatro cenários — em 1 milhão, por exemplo, fica entre `105,3%` e `106,1%`. Além disso, a métrica de validação mostrou que o tempo médio de inspeção por mensagem convergiu exatamente para `0,080 ms` nas quatro ferramentas."
> "Isso confirma que nenhum dos coletores interfere de forma perceptível na capacidade de processamento do WAF."

↪️ **Transição:** "Seguindo a ordem do Capítulo 3, vejamos agora o consumo de CPU e de memória do próprio observador."

---

## SLIDE 14 — Consumo de CPU do próprio observador · ~0:50

🎯 **Objetivo:** apresentar com rigor científico por que a CPU do observador é tratada como evidência qualitativa complementar (inconclusiva quantitativamente).

🗣️ **O que dizer:**
> "Na CPU do próprio processo observador, observamos médias baixas em todos os 16 grupos — de `0,05%` a `5,05%` —, porém quase sempre acompanhadas de intervalos de confiança largos, da ordem da própria média, causados por picos isolados de escalonamento."
> "Isso ocorre pela granularidade da amostragem do `psutil` em intervalos curtos de 1 segundo e pela disputa de núcleos entre os contêineres. Além disso, no caso do Docker, quem faz a leitura do *cgroup* é o processo externo `dockerd`, cujo consumo de CPU não entra na conta do observador. Por honestidade científica, tratamos essa métrica como inconclusiva quantitativamente."

↪️ **Transição:** "Já no consumo de memória do observador, a separação entre as quatro arquiteturas é nítida e altamente estável."

---

## SLIDE 15 — Consumo de memória do observador e do WAF · ~1:00

🎯 **Objetivo:** destacar a diferença de footprint de memória do observador (13,6 vs. 15,0 vs. 24,7 vs. 30,8 MB) e a ressalva do cgroup vs. RSS na memória do WAF.

🗣️ **O que dizer:**
> "A memória do observador representa o custo fixo de manter a ferramenta ativa, e permanece constante em todos os volumes com intervalos de confiança inferiores a `0,06 MB`:"
> "• O **Sysstat** foi o mais enxuto, com `13,6 MB`;"
> "• O **eBPF** ficou muito próximo, com `15,0 MB` — vale destacar que a nossa migração do antigo arcabouço BCC/LLVM para `libbpf + CO-RE` reduziu a memória do eBPF em 92%, caindo de `~196 MB` para `15 MB`;"
> "• O **Prometheus** consumiu `24,7 MB` (+81% que o Sysstat), reflexo direto do servidor HTTP e da biblioteca `prometheus_client`;"
> "• E o **Docker** consumiu `30,8 MB` (+126% que o Sysstat), devido ao SDK Python do Docker e suas dependências."
> "Sobre a memória do WAF: no eBPF, Sysstat e Prometheus ela cresce igualmente de `28 MB` a `46 MB` (medida como RSS pelo `psutil`). No Docker os números aparecem ~6 a 8 MB menores porque o *cgroup* contabiliza `usage − inactive_file` e não RSS — portanto são grandezas distintas e não comparáveis."

↪️ **Transição:** "Durante a análise das métricas de validação, notamos um ponto importante sobre a vazão do WAF nos volumes maiores, que motivou uma investigação adicional."

---

## SLIDE 16 — Análise de sensibilidade da vazão e coleta com 100% de N · ~1:15

🎯 **Objetivo:** mostrar maturidade experimental: explicar por que a coleta oficial inspecionou 62–88% de N nos volumes maiores e mostrar a bateria extra de 480 execuções que atingiu 100% de N mantendo a mesma conclusão.

🗣️ **O que dizer:**
> "Na coleta oficial, com 1 processo de WAF e 1 de cliente, a vazão sustentada foi de 7 a 8 mil mensagens por segundo. Com isso, dentro da janela `DURATION`, o WAF processou 100% das 100 mil mensagens, mas de 62% a 88% nos volumes de 500 mil a 2 milhões. Embora a carga processada tenha sido idêntica entre as 4 ferramentas, investigamos a causa desse teto."
> "Na Tabela à esquerda, variando a configuração no eBPF em $N = 1$ milhão, descobrimos dois gargalos simultâneos: o processo único do WAF e o uso do *pool* de *threads* a cada leitura no cliente. Quando combinamos **4 processos de WAF, 4 de cliente e leitura direta no laço de eventos**, o WAF inspecionou **100% das mensagens**."
> "Repetimos então a bateria inteira nessa configuração — **mais 480 execuções** (Tabela à direita). Em todas as 16 combinações o WAF inspecionou 100% de $N$, e **a ordem entre as ferramentas se manteve inalterada em todos os volumes**: eBPF (`~0,90 ms`) < Sysstat (`~1,01 ms`) < Prometheus (`~1,04 ms`) < Docker (`~2,65 ms`). O acréscimo de `~0,4 ms` nos três primeiros ocorre porque o `psutil` passa a consultar 4 processos `waf.py` por sonda em vez de 1. Isso prova que a conclusão do trabalho independe de o WAF processar a fração ou a totalidade de $N$."

↪️ **Transição:** "Consolidando todas as dimensões analisadas, chegamos à tabela de síntese."

---

## SLIDE 17 — Síntese comparativa das quatro abordagens · ~1:00

🎯 **Objetivo:** resumir a Tabela 4 do TCC e apontar quando cada ferramenta é indicada.

🗣️ **O que dizer:**
> "Em síntese: o **eBPF** vence na métrica primária de tempo de resposta em todos os cenários e tem memória baixa (`15 MB`), exigindo em contrapartida modo privilegiado, BTF e `pid:host`."
> "O **Sysstat** tem o menor consumo de memória (`13,6 MB`), não exige privilégio de kernel e fica apenas `~0,07 ms` atrás do eBPF."
> "O **Prometheus** tem tempo próximo ao Sysstat, mas paga `+11 MB` de RAM pelo servidor HTTP — custo que só se justifica quando integrado a um servidor Prometheus fazendo coleta ativa."
> "E a **API do Docker** tem a vantagem operacional de dispensar `pid:host` e expor métricas por contêiner, mas cobra um tempo de resposta cinco vezes maior (`~2,5 ms`) e o maior consumo de memória (`30,8 MB`)."

↪️ **Transição:** "Isso nos leva às conclusões gerais do trabalho."

---

## SLIDE 18 — Conclusões · ~1:00

🎯 **Objetivo:** responder diretamente à hipótese e destacar as contribuições concretas do TCC.

🗣️ **O que dizer:**
> "Concluímos que **a hipótese inicial foi confirmada para a métrica primária**: por operar no kernel, o eBPF entrega o menor tempo de resposta em todos os volumes (**−13% vs. Sysstat, −15% vs. Prometheus e −80% vs. Docker**), sem impor sobrecarga adicional à CPU do WAF."
> "Em termos práticos, mostramos que o ganho do eBPF sobre o *polling* de `/proc` é real e estatisticamente significativo, porém moderado em termos absolutos (`0,07 a 0,09 ms`), devendo ser ponderado frente à maior complexidade de implementação e privilégios de kernel. Já a comparação com a API do Docker demonstrou empiricamente como camadas intermediárias de IPC e serialização (`dockerd`) elevam em 30 vezes o custo de acessar métricas que o próprio kernel mantém nos *cgroups*."
> "Como contribuições concretas, entregamos um benchmark de código aberto totalmente reprodutível com **960 execuções**, a implementação eBPF enxuta com `libbpf + CO-RE`, e o dashboard interativo público."

↪️ **Transição:** "Para finalizar, destacamos as limitações do estudo e os trabalhos futuros."

---

## SLIDE 19 — Limitações e trabalhos futuros · ~0:45

🎯 **Objetivo:** demonstrar rigor metodológico reconhecendo as ressalvas e apontando os próximos passos diretos.

🗣️ **O que dizer:**
> "Entre as limitações documentadas: o tráfego flui em *loopback*, sem o overhead de placas de rede físicas; o RTT do Docker inclui a consulta síncrona ao `dockerd` (não usamos cache em segundo plano para não tornar a comparação desigual); as métricas de WAF no Docker vêm do *cgroup* e não são diretamente comparáveis ao RSS do `psutil`; e o Prometheus foi avaliado como *exporter*, sem *scraping* ativo."
> "Como trabalhos futuros, propomos: **(i)** implementar um coletor que leia os arquivos do *cgroup* v2 diretamente em `/sys/fs/cgroup/`, sem passar pelo `dockerd`; **(ii)** avaliar um WAF de maior vazão em processo único; **(iii)** medir o impacto do monitoramento na latência fim a fim das requisições do WAF; e **(iv)** estender o benchmark para cadeias completas de VNFs (SFCs) e hooks XDP/TC."

↪️ **Transição:** "Com isso encerramos a nossa apresentação."

---

## SLIDE 20 — Encerramento · ~0:25

🎯 **Objetivo:** agradecer à banca e deixar os links visíveis.

🗣️ **O que dizer:**
> "Todo o código-fonte, os dados brutos das execuções e o painel interativo estão abertos nos links da tela. Muito obrigado pela atenção da banca, e estamos à disposição para as perguntas e considerações."

---

## PERGUNTAS PROVÁVEIS DA BANCA (Defesa Final)

1. **"Por que o coletor Docker ficou tão mais lento (~2,5 ms) se o cgroup também está no kernel?"**
   → Porque o observador não lê o arquivo do *cgroup* diretamente; ele usa o SDK oficial do Docker (`container.stats(stream=False, one_shot=True)`), que faz uma requisição HTTP sobre o socket Unix `/var/run/docker.sock` até o *daemon* `dockerd` (em Go). O `dockerd` lê vários arquivos do *cgroup*, monta um JSON grande com todas as estatísticas do contêiner e serializa de volta. Na nossa análise isolada (`bench_docker_cgroup.py`), ler `cpu.stat` e `memory.current` direto do `/sys/fs/cgroup` levou apenas `0,04 ms`, enquanto passar pela API do daemon levou `1,4 a 1,7 ms`.

2. **"Por que vocês não colocaram uma thread em background ou cache no coletor Docker para responder rápido ao UDP?"**
   → Explicamos isso na Seção 3.1: se o Docker respondesse a partir de um valor em cache, o RTT mediria apenas a leitura de uma variável em memória local e entregaria uma métrica defasada, enquanto eBPF, Sysstat e Prometheus coletam a métrica fresca no exato instante da requisição UDP. Isso tornaria a comparação metodologicamente injusta.

3. **"Na primeira coleta de 480 execuções, 22% tiveram `inspect_count = 0`. Como vocês resolveram isso?"**
   → Identificamos que o WAF abria e escrevia `waf_metrics.json` diretamente; quando a sonda UDP lia o arquivo no exato instante da escrita, pegava o arquivo truncado e retornava zero. Corrigimos o WAF para fazer escrita atômica (grava em arquivo temporário e aplica `os.replace`) e **repetimos integralmente as 480 execuções**. Na bateria oficial apresentada no TCC, 0 de 480 execuções tiveram falha, e os RTTs bateram dentro do IC95% com a primeira coleta.

4. **"Por que o RTT aumentou de ~0,50 ms para ~0,90 ms no eBPF na coleta com 4 processos do WAF (Seção 3.6)?"**
   → Porque o observador eBPF (assim como Sysstat e Prometheus) usa `psutil` para consultar CPU e memória de todos os processos `waf.py` ativos a cada sonda UDP. Com 4 processos do WAF em vez de 1, o custo de varrer os processos no `/proc` via `psutil` quadruplica, somando `~0,4 ms` ao RTT dos três coletores. Já o Docker subiu apenas `~0,15 ms` (`2,50 → 2,65 ms`) porque consulta o *cgroup* do contêiner inteiro em uma única chamada. Ainda assim, a ordem `eBPF < Sysstat < Prometheus < Docker` se manteve em 100% dos volumes.

5. **"Como vocês reduziram a memória do eBPF de ~196 MB para 15 MB?"**
   → Na versão preliminar usávamos BCC (`python3-bpfcc`), que embute o compilador LLVM/Clang inteiro dentro do processo Python em tempo de execução. Migramos para `libbpf + CO-RE` (*Compile Once – Run Everywhere*): o programa C (`ebpf_kern.c`) é compilado com `clang` e `bpftool` usando o BTF do kernel antes de iniciar o Python, e o observador carrega o `.o` via `ctypes` + `libbpf.so.1`, reduzindo 92% do uso de RAM.
