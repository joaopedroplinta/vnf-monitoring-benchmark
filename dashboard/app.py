"""Explorador dos resultados do TCC. Uso: streamlit run dashboard/app.py."""
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from analytics import LABEL, confidence_separated, number, summary, volume

ROOT = Path(__file__).parent
# Tons consistentes com contraste nas superfícies dos dois temas.
COLOR = {"eBPF": "#20a0b0", "Sysstat": "#b98423", "Prometheus": "#8184de", "Docker": "#ce667c"}
METRICS = {
    "cpu_waf": "CPU do WAF (%)", "mem_waf_mb": "Memória do WAF (MB)",
    "cpu_obs": "CPU do observador (%)", "mem_obs_mb": "Memória do observador (MB)",
}
CHART_CONFIG = {
    "displaylogo": False, "scrollZoom": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}
NETWORK_ICON = '<svg viewBox="0 0 40 40" fill="none" aria-hidden="true"><path d="M10 10L30 10L20 30Z" stroke="currentColor" stroke-width="1.5"/><path d="M10 10L20 18L30 10M20 18V30" stroke="currentColor" stroke-width="1.5"/><circle cx="10" cy="10" r="4" fill="var(--sidebar)" stroke="currentColor" stroke-width="2"/><circle cx="30" cy="10" r="4" fill="var(--sidebar)" stroke="currentColor" stroke-width="2"/><circle cx="20" cy="30" r="4" fill="var(--sidebar)" stroke="currentColor" stroke-width="2"/><circle cx="20" cy="18" r="2" fill="currentColor"/></svg>'

st.set_page_config(page_title="VNF Lab | Benchmark de monitoramento", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
st.markdown(f"<style>{(ROOT / 'style.css').read_text()}</style>", unsafe_allow_html=True)


def html(markup):
    st.markdown(markup, unsafe_allow_html=True)


def title(text, sub="", direction=""):
    tag = f'<span class="direction">{escape(direction)}</span>' if direction else ""
    html(f'<div class="section-heading"><h2>{escape(text)}</h2>{tag}</div>'
         f'<p class="section-sub">{escape(sub)}</p>')


def style(fig, height=310, legend=True):
    fig.update_layout(
        template=None, height=height, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", separators=",.",
        font=dict(family="Manrope, sans-serif", size=12),
        margin=dict(l=10, r=15, t=20, b=10), showlegend=legend,
        legend=dict(orientation="h", y=1.16, x=0, title=None, font_size=11),
        hoverlabel=dict(font_size=12),
        bargap=0.3, bargroupgap=0.1,
    )
    fig.update_xaxes(showgrid=False, title=None, automargin=True)
    fig.update_yaxes(zeroline=False, automargin=True, title_font_size=11)
    return fig


def plot(fig, key, height=310, legend=True):
    st.plotly_chart(style(fig, height, legend), width="stretch", config=CHART_CONFIG,
                    theme="streamlit", key=key)


@st.cache_data
def load(path, modified):
    data = pd.read_csv(path)
    data["Ferramenta"] = data["tool"].map(LABEL).fillna(data["tool"])
    data["N"] = data["n"].map(volume)
    return data


def reset_filters():
    st.session_state["tools"] = list(LABEL.values())
    st.session_state["volumes"] = all_volumes
    st.session_state["log"] = False


def bar_chart(data, metric, logarithmic=False):
    s = summary(data, metric)
    fig = px.bar(s, x="N", y="mean", color="Ferramenta", barmode="group", error_y="ci",
                 color_discrete_map=COLOR, labels={"mean": METRICS.get(metric, "RTT médio (ms)")},
                 category_orders={"N": list(s["N"].unique()), "Ferramenta": list(LABEL.values())},
                 custom_data=["count", "ci"])
    fig.update_traces(marker_line_width=0,
                      error_y=dict(thickness=1.2, width=3),
                      hovertemplate="%{x}<br>Média: %{y:.3f}<br>IC95%: ±%{customdata[1]:.3f}<br>%{customdata[0]} execuções<extra>%{fullData.name}</extra>")
    if logarithmic:
        fig.update_yaxes(type="log")
    return fig


data_path = ROOT / "data.csv"
if not data_path.exists():
    st.error("Os resultados ainda não foram preparados. Execute `python3 dashboard/build_data.py` na pasta do projeto.")
    st.stop()
df = load(str(data_path), data_path.stat().st_mtime_ns)
all_volumes = sorted(df["n"].unique().tolist())
st.session_state.setdefault("tools", list(LABEL.values()))
st.session_state.setdefault("volumes", all_volumes)

with st.sidebar:
    html(f'<div class="brand">{NETWORK_ICON}<div><strong>VNF Lab</strong><span>Benchmark de monitoramento</span></div></div>')
    st.caption("Claro ou escuro: escolha no menu Tema, no canto superior direito.")
    html('<div class="sidebar-label">Explore o experimento</div><div class="sidebar-note">Compare as ferramentas sob diferentes volumes de carga.</div>')
    tools = st.multiselect("Ferramentas", list(LABEL.values()), key="tools")
    ns = st.multiselect("Volume nominal de mensagens", all_volumes,
                        format_func=number, key="volumes",
                        help="N é o volume do arquivo de payloads, não o total efetivamente processado pelo WAF.")
    log = st.toggle("Escala logarítmica de RTT", key="log", help="Aplique aos gráficos de latência para comparar ferramentas em ordens de grandeza diferentes.")
    st.button("Restaurar filtros", on_click=reset_filters, width="stretch", icon=":material/restart_alt:")
    html('<div class="sidebar-label">Guia de cores</div><div class="tool-key">' + "".join(
        f'<span><i class="tool-dot" style="--tool-color:{color}"></i>{name}</span>' for name, color in COLOR.items()
    ) + '</div>')
    html('<div class="sidebar-meta"><strong>Sobre o estudo</strong>'
         '<p class="study-name">Monitoramento de Funções Virtualizadas de Redes: um estudo comparativo entre ferramentas de extração de comportamento</p>'
         '<dl><dt>Autores</dt><dd>João Pedro dos Santos Henrique Plinta<br>Rafael Correia Alves</dd>'
         '<dt>Orientador</dt><dd>Prof. Guilherme Werneck de Oliveira</dd></dl>'
         '<p class="study-institution">TCC de Ciência da Computação<br>IFPR Campus Pinhais · 2026</p>'
         '<a href="https://github.com/joaopedroplinta/vnf-monitoring-benchmark" target="_blank" rel="noopener noreferrer">Ver repositório no GitHub</a></div>')

view = df[df["Ferramenta"].isin(tools) & df["n"].isin(ns)].copy()
html('<div class="masthead"><span class="context">Pesquisa experimental / Monitoramento de redes</span><span class="status">Resultados do benchmark</span></div>'
     '<div class="hero"><h1>Quanto custa monitorar uma VNF?</h1>'
     '<p>Quatro abordagens, o mesmo WAF. Explore o tempo de resposta do observador e o consumo de recursos em cada cenário.</p></div>')
if view.empty:
    st.info("Nenhum resultado neste recorte. Selecione pelo menos uma ferramenta e um volume na lateral, ou restaure os filtros.")
    st.button("Mostrar todos os resultados", on_click=reset_filters, type="primary")
    st.stop()

ordered_tools = [tool for tool in LABEL.values() if tool in tools]
rtt = view.groupby("Ferramenta")["rtt_ms"].mean().sort_values()
memory = view.groupby("Ferramenta")["mem_obs_mb"].mean().dropna().sort_values()
best = rtt.index[0]
counts = view.groupby(["Ferramenta", "n"]).size()
reps = str(counts.iloc[0]) if counts.nunique() == 1 else f'{counts.min()}–{counts.max()}'
html(f'<div class="study-strip"><div><strong>{number(len(view))}</strong><span>execuções no recorte</span></div>'
     f'<div><strong>{len(ordered_tools)} <small>×</small> {view["n"].nunique()}</strong><span>ferramentas × volumes</span></div>'
     f'<div><strong>{reps}</strong><span>repetições por combinação</span></div>'
     '<div><strong>95<small>%</small></strong><span>nível de confiança dos intervalos</span></div></div>')

overview, latency, resources, runs, data_tab, method = st.tabs([
    "Visão geral", "Latência", "Recursos", "Execuções", "Dados", "Metodologia",
])

with overview:
    left, right = st.columns([1.7, 1], gap="medium")
    with left, st.container(key="overview-trend"):
        title("A resposta muda com a carga?", "RTT médio do observador por volume nominal · média ± IC95%", "Menor é melhor")
        s = summary(view, "rtt_ms")
        fig = px.line(s, x="N", y="mean", color="Ferramenta", markers=True, error_y="ci",
                      color_discrete_map=COLOR, labels={"mean": "RTT médio (ms)"},
                      category_orders={"Ferramenta": ordered_tools, "N": list(s["N"].unique())},
                      line_dash="Ferramenta", symbol="Ferramenta", custom_data=["count", "ci"])
        fig.update_traces(line_width=2.5, marker_size=8, error_y=dict(thickness=1.1, width=3),
                          hovertemplate="%{x}<br>%{y:.3f} ms ± %{customdata[1]:.3f}<br>%{customdata[0]} execuções<extra>%{fullData.name}</extra>")
        fig.update_yaxes(type="log" if log else "linear", rangemode="tozero")
        plot(fig, "overview-trend-chart", 305)
    with right, st.container(key="overview-ranking"):
        title("Tempo de resposta por ferramenta", "Média das execuções nos volumes selecionados", "Menor é melhor")
        ranking = ""
        for tool, value in rtt.items():
            note = 'Menor média neste recorte' if tool == best else f'{number(value / rtt.iloc[0], 2)}× o tempo de {best}'
            ranking += (
                f'<div class="rank-item" style="--tool-color:{COLOR[tool]};--bar-width:{value / rtt.max() * 100:.2f}%">'
                f'<div class="rank-head"><span class="name"><i class="tool-dot"></i>{tool}</span><strong>{number(value, 3)} <small>ms</small></strong></div>'
                '<div class="rank-track"><div class="rank-fill"></div></div>'
                f'<div class="rank-note"><span class="{"winner" if tool == best else ""}">{note}</span><span>{number(len(view[view["Ferramenta"] == tool]))} exec.</span></div></div>'
            )
        html(ranking)
        st.caption("Este resumo combina volumes. Consulte os intervalos por volume no gráfico ao lado.")
    left, right = st.columns([1.7, 1], gap="medium")
    with left, st.container(key="overview-memory"):
        title("Memória para observar o WAF", "Consumo médio do observador nos volumes selecionados", "Menor é melhor")
        fig = px.bar(x=memory.values, y=memory.index, orientation="h", color=memory.index,
                     color_discrete_map=COLOR, text=[f"{number(v, 2)} MB" for v in memory.values],
                     labels={"x": "Memória média (MB)", "y": "Ferramenta"})
        fig.update_traces(textposition="outside", cliponaxis=False, width=0.48,
                          hovertemplate="%{y}<br>%{x:.3f} MB<extra></extra>")
        fig.update_yaxes(autorange="reversed", title=None)
        fig.update_xaxes(range=[0, memory.max() * 1.3], title="Memória média (MB)")
        plot(fig, "overview-memory-chart", 240, False)
    with right, st.container(key="overview-findings"):
        title("O que este recorte mostra", "Conclusões calculadas a partir dos filtros atuais")
        if len(rtt) > 1:
            runner = rtt.index[1]
            advantage = (1 - rtt.iloc[0] / rtt.iloc[1]) * 100
            html(f'<div class="finding-lead">{best} tem RTT médio {number(advantage, 1)}% menor.</div>'
                 f'<p class="finding-text">Em relação a {runner}, a segunda menor média entre as ferramentas selecionadas.</p>')
            separate = confidence_separated(view, best, runner)
            ci_text = (f"Os IC95% de {best} e {runner} não se sobrepõem em nenhum volume selecionado."
                       if separate else "A separação dos IC95% não se confirma em todos os volumes selecionados. Consulte a análise por volume.")
            html(f'<div class="finding-divider"><div class="finding-label">Leitura dos intervalos</div><p class="finding-text">{ci_text}</p></div>')
        else:
            html(f'<div class="finding-lead">{best}, em detalhe.</div><p class="finding-text">Selecione outra ferramenta para comparar os tempos de resposta.</p>')
        html(f'<div class="finding-divider"><div class="finding-label">Menor consumo de memória do observador</div>'
             f'<p class="finding-text">{memory.index[0]}: {number(memory.iloc[0], 2)} MB em média neste recorte.</p></div>')

with latency:
    cards = ""
    for tool in ordered_tools:
        value = rtt[tool]
        note = "Menor média no recorte" if tool == best else f'{number(value / rtt.iloc[0], 2)}× o tempo de {best}'
        cards += f'<div class="comparison-card"><div class="tool"><i class="tool-dot" style="--tool-color:{COLOR[tool]}"></i>{tool}</div><div class="value">{number(value, 3)} <small>ms</small></div><div class="detail">{note}</div></div>'
    html(f'<div class="comparison-grid" style="--columns:{len(ordered_tools)}">{cards}</div>')
    with st.container(key="latency-bars"):
        title("Tempo de resposta por volume", "Barras de erro representam o IC95% da média de cada combinação.", "Menor é melhor")
        plot(bar_chart(view, "rtt_ms", log), "latency-bars-chart", 380)
    with st.container(key="latency-box"):
        a, b = st.columns([3, 1])
        with a:
            title("Como as execuções se distribuem?", "Cada ponto representa o RTT médio de uma execução do experimento.")
        with b:
            can_focus = "Docker" in tools and len(tools) > 1
            focus = st.toggle("Detalhar sem Docker", value=False, disabled=not can_focus) and can_focus
        distribution = view[view["Ferramenta"] != "Docker"] if focus else view
        fig = px.box(distribution.sort_values("n"), x="N", y="rtt_ms", color="Ferramenta",
                     points="all", color_discrete_map=COLOR, labels={"rtt_ms": "RTT médio da execução (ms)"},
                     category_orders={"Ferramenta": ordered_tools})
        fig.update_traces(marker_size=3, jitter=0.25)
        fig.update_yaxes(type="log" if log else "linear")
        plot(fig, "latency-box-chart", 370)

with resources:
    title("O custo em CPU e memória", "Selecione qual componente e recurso você quer comparar.")
    metric = st.selectbox("Métrica de recursos", list(METRICS), index=3, format_func=METRICS.get)
    if metric in ("mem_waf_mb", "cpu_waf") and "Docker" in tools:
        st.info("No Docker, os recursos do WAF são medidos pelo cgroup. Nas demais ferramentas, pelo processo (psutil). As medições não são diretamente comparáveis.", icon=":material/info:")
    if metric == "cpu_obs":
        st.info("A CPU do observador é ruidosa neste experimento. Os intervalos podem ser da ordem da média; esta métrica não permite uma conclusão firme sobre a melhor ferramenta.", icon=":material/info:")
    with st.container(key="resources-chart"):
        title(METRICS[metric], "Média por volume nominal · barras de erro: IC95%")
        plot(bar_chart(view, metric), "resources-plot", 400)
    st.caption("CPU pode ultrapassar 100% quando o processo utiliza mais de um núcleo.")

with runs:
    title("Da média às execuções individuais", "Compare a estabilidade do observador entre repetições de uma mesma carga.")
    selected_n = st.selectbox("Volume das execuções", sorted(view["n"].unique()), format_func=number)
    with st.container(key="runs-chart"):
        title(f"RTT de cada execução · {volume(selected_n)} mensagens", "Os pontos são execuções independentes, não uma série temporal de monitoramento.")
        fig = px.line(view[view["n"] == selected_n].sort_values("run"), x="run", y="rtt_ms",
                      color="Ferramenta", markers=True, color_discrete_map=COLOR,
                      line_dash="Ferramenta", symbol="Ferramenta",
                      labels={"run": "Execução", "rtt_ms": "RTT médio (ms)"},
                      category_orders={"Ferramenta": ordered_tools})
        fig.update_traces(line_width=1.8, marker_size=5,
                          hovertemplate="Execução %{x}<br>%{y:.3f} ms<extra>%{fullData.name}</extra>")
        fig.update_yaxes(type="log" if log else "linear")
        fig.update_xaxes(title="Execução", dtick=5)
        plot(fig, "runs-plot", 420)

with data_tab:
    title("Resultados disponíveis para conferência", "A tabela e o CSV respeitam as ferramentas e os volumes selecionados na lateral.")
    raw = view.drop(columns=["Ferramenta", "N"]).sort_values(["tool", "n", "run"])
    st.download_button("Baixar este recorte em CSV", raw.to_csv(index=False),
                       "resultados_vnf.csv", "text/csv", icon=":material/download:")
    with st.container(key="data-table"):
        st.dataframe(raw, width="stretch", hide_index=True, height=430,
                     column_config={
                         "tool": st.column_config.TextColumn("Ferramenta"),
                         "n": st.column_config.NumberColumn("N nominal", format="localized"),
                         "run": st.column_config.NumberColumn("Execução", format="%d"),
                         "rtt_ms": st.column_config.NumberColumn("RTT (ms)", format="%.4f"),
                         "rtt_std_ms": st.column_config.NumberColumn("Desvio RTT (ms)", format="%.4f"),
                         "mem_obs_mb": st.column_config.NumberColumn("Memória observador (MB)", format="%.2f"),
                         "cpu_obs": st.column_config.NumberColumn("CPU observador (%)", format="%.3f"),
                         "mem_waf_mb": st.column_config.NumberColumn("Memória WAF (MB)", format="%.2f"),
                         "cpu_waf": st.column_config.NumberColumn("CPU WAF (%)", format="%.2f"),
                     })
    with st.expander("Como interpretar as colunas"):
        st.markdown("**RTT:** tempo de resposta do observador ao probe UDP. **N nominal:** tamanho do arquivo de payloads. **inspect_count:** mensagens efetivamente inspecionadas. **CPU e memória:** médias por execução. **bytes_rx/tx:** tráfego observado; eBPF mede a porta 8080, enquanto os demais medem toda a interface loopback.")

with method:
    title("Um experimento, quatro formas de observar", "O mesmo WAF e o mesmo probe em todas as abordagens.")
    html('<div class="pipeline"><div><strong>Cliente</strong><p>Envia payloads por TCP: 60% benignos e 40% maliciosos.</p></div>'
         '<div><strong>WAF</strong><p>Inspeciona os payloads em uma função de rede virtualizada simplificada.</p></div>'
         '<div><strong>Observador</strong><p>Coleta as métricas com a ferramenta em teste e responde por UDP.</p></div>'
         '<div><strong>Probe</strong><p>Faz uma consulta por segundo e mede o tempo de resposta do observador.</p></div></div>')
    st.markdown("O **RTT mede o tempo de resposta do observador**. O consumo de CPU e memória do WAF ajuda a caracterizar o impacto no processo monitorado.")
    st.table(pd.DataFrame({"Ferramenta": list(LABEL.values()), "Abordagem": [
        "kprobes no kernel com libbpf + CO-RE", "Leitura de /proc/net/dev em espaço de usuário",
        "Leitura de /proc/net/dev com endpoint HTTP /metrics ativo", "container.stats() pela API do Docker (cgroups)",
    ]}))
    with st.expander("Estatística e leitura dos gráficos", expanded=True):
        st.markdown("Os gráficos por volume mostram **média ± intervalo de confiança de 95%**, calculado com t de Student para as 30 repetições originais. Um IC descreve a incerteza da média; o boxplot mostra a variação entre execuções. Os resumos da visão geral agregam as execuções dos volumes selecionados. A ausência de sobreposição entre ICs é verificada por volume e não substitui uma análise causal.")
    with st.expander("Limitações do experimento", expanded=True):
        st.markdown("- Tráfego em **loopback**, com cliente, WAF e observador compartilhando recursos da máquina.\n- Coletas em lotes não intercalados: o estado da máquina pode influenciar as diferenças.\n- N é **nominal**: nos volumes maiores, o WAF não processa todas as mensagens no tempo disponível.\n- CPU e memória do WAF no Docker vêm do **cgroup**, enquanto as demais vêm do processo.\n- Prometheus foi avaliado como exporter, **sem scraping** por um servidor.\n- A CPU do observador apresentou alta variabilidade e é inconclusiva.")
    st.caption("João Pedro dos Santos Henrique Plinta e Rafael Correia Alves · Orientação: Prof. Guilherme Werneck de Oliveira · IFPR Campus Pinhais, 2026")

html(f'<div class="footer-line"><span>VNF Lab · Estudo comparativo de monitoramento</span>'
     f'<span>{number(len(view))} de {number(len(df))} execuções · Dados experimentais, sem atualização em tempo real</span></div>')
