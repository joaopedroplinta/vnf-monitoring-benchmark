#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a apresentacao da Defesa Final do TCC em PPTX editavel — tema CLARO Institucional (IFPR).
Atualizado com as 4 ferramentas (eBPF, Sysstat, Prometheus, API do Docker),
480 execucoes oficiais + 480 execucoes da analise de sensibilidade, e revisoes pos-pre-banca.

Caixas de texto, tabelas e formas nativas (editaveis no PowerPoint/LibreOffice/Canva).
Reaproveita os graficos e logos em docs/imagens/.

Uso:  python3 docs/apresentacao/gerar_pptx.py
Saida: docs/apresentacao/apresentacao_tcc.pptx
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE

# ---- caminhos ----
BASE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.normpath(os.path.join(BASE, "..", "imagens"))
OUT = os.path.join(BASE, "apresentacao_tcc.pptx")
FONT = "Arial"

# ---- paleta clara institucional (IFPR + cores das 4 ferramentas) ----
BG        = RGBColor(0xF6, 0xF8, 0xFB)   # fundo claro suave
PANEL     = RGBColor(0xFF, 0xFF, 0xFF)   # cartao branco puro
PANEL_ALT = RGBColor(0xEE, 0xF3, 0xF8)   # cartao secundario / linha alternada
BORDER    = RGBColor(0xD0, 0xDB, 0xE5)   # borda sutil cinza-azulada
TXT       = RGBColor(0x18, 0x28, 0x3D)   # texto principal azul-petroleo escuro
MUT       = RGBColor(0x52, 0x64, 0x7C)   # texto secundario

# Cores institucionais e por ferramenta
IFPR_VERDE = RGBColor(0x2F, 0x9E, 0x41)  # verde oficial IFPR
IFPR_ESCURO = RGBColor(0x1B, 0x5E, 0x20) # verde escuro para cabecalhos/destaque
VERDE     = RGBColor(0x1E, 0x82, 0x38)   # eBPF / destaque positivo (bom contraste no claro)
AZUL      = RGBColor(0x15, 0x65, 0xC0)   # Sysstat / acento institucional
LARANJA   = RGBColor(0xD9, 0x77, 0x06)   # Prometheus / alerta
ROXO      = RGBColor(0x7B, 0x1F, 0xA2)   # Docker API
BRANCO    = RGBColor(0xFF, 0xFF, 0xFF)
ROW_HI    = RGBColor(0xE3, 0xF5, 0xE6)   # destaque verde claro para linha vencedora na tabela

# ---- 16:9 ----
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]
TOTAL_SLIDES = 21
F = 1.0   # fator de escala de fonte, ajustado por slide


# ------------------------------------------------------------------ helpers
def slide():
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    return s


def _runs(p, runs, size, color, bold, italic):
    if isinstance(runs, str):
        runs = [(runs, {})]
    for txt, kw in runs:
        r = p.add_run()
        r.text = txt
        r.font.size = Pt(round(kw.get("size", size) * F * 2) / 2)
        r.font.bold = kw.get("bold", bold)
        r.font.italic = kw.get("italic", italic)
        r.font.color.rgb = kw.get("color", color)
        r.font.name = FONT


def textbox(s, left, top, width, height, anchor=MSO_ANCHOR.TOP, autoshrink=True):
    tb = s.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    if autoshrink:
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    tf.margin_left = Pt(4); tf.margin_right = Pt(4)
    tf.margin_top = Pt(2); tf.margin_bottom = Pt(2)
    return tb, tf


def para(tf, runs, size=17, color=TXT, bold=False, italic=False, align=PP_ALIGN.LEFT,
         space_after=6, bullet=False, first=False, accent=IFPR_VERDE):
    p = tf.paragraphs[0] if (first and not tf.paragraphs[0].runs) else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    if bullet:
        r = p.add_run()
        r.text = "▸  "
        r.font.size = Pt(round(size * F * 2) / 2)
        r.font.color.rgb = accent
        r.font.name = FONT
        r.font.bold = True
    _runs(p, runs, size, color, bold, italic)
    return p


def header(s, kicker, ttl, num=None):
    # Cabeçalho e rodapé têm tamanho fixo (título 32, kicker 15, rodapé 14): o F de cada slide só vale para o conteúdo.
    global F
    f_slide, F = F, 1.0
    try:
        _header(s, kicker, ttl)
    finally:
        F = f_slide


def _header(s, kicker, ttl, num=None):
    num = len(prs.slides._sldIdLst)
    # Barra superior fina verde IFPR
    topbar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, Inches(0.08))
    topbar.fill.solid(); topbar.fill.fore_color.rgb = IFPR_VERDE
    topbar.line.fill.background(); topbar.shadow.inherit = False

    # Kicker pequeno em maiusculas
    tb, tf = textbox(s, Inches(0.65), Inches(0.32), Inches(9.5), Inches(0.32), autoshrink=False)
    para(tf, [(kicker.upper(), {"size": 15, "color": IFPR_VERDE, "bold": True})], first=True)

    # Logo IFPR discreto no canto superior direito
    logo_path = os.path.join(IMG, "logo-ifpr.png")
    if os.path.exists(logo_path):
        s.shapes.add_picture(logo_path, Inches(10.38), Inches(0.22), width=Inches(2.35))

    # Titulo grande
    tb2, tf2 = textbox(s, Inches(0.62), Inches(0.62), Inches(9.7), Inches(0.85), autoshrink=True)
    para(tf2, [(ttl, {"size": 32, "color": TXT, "bold": True})], first=True)

    # Regra de acento
    rule = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(1.48), Inches(1.3), Pt(3.5))
    rule.fill.solid(); rule.fill.fore_color.rgb = IFPR_VERDE; rule.line.fill.background()
    rule.shadow.inherit = False

    # Linha divisoria fina no rodape
    foot_line = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(6.95), Inches(12.03), Pt(1))
    foot_line.fill.solid(); foot_line.fill.fore_color.rgb = BORDER; foot_line.line.fill.background()
    foot_line.shadow.inherit = False

    # Rodape esquerda
    tb4, tf4 = textbox(s, Inches(0.65), Inches(7.02), Inches(8.5), Inches(0.35), autoshrink=False)
    para(tf4, [("Defesa de TCC · Ciência da Computação · IFPR Campus Pinhais · 2026", {"size": 14, "color": MUT})], first=True)

    # Numero do slide
    tb3, tf3 = textbox(s, Inches(11.5), Inches(7.02), Inches(1.18), Inches(0.35), autoshrink=False)
    para(tf3, [(f"{num:02d} / {TOTAL_SLIDES:02d}", {"size": 14, "color": MUT, "bold": True})], align=PP_ALIGN.RIGHT, first=True)


def card(s, left, top, width, height, accent, heading, lines, head_size=15, line_size=13, bg_color=PANEL):
    box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    box.fill.solid(); box.fill.fore_color.rgb = bg_color
    box.line.color.rgb = BORDER; box.line.width = Pt(1)
    box.shadow.inherit = False

    # Barra de acento a esquerda
    strip = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, Inches(0.08), height)
    strip.fill.solid(); strip.fill.fore_color.rgb = accent; strip.line.fill.background()
    strip.shadow.inherit = False

    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Pt(14); tf.margin_top = Pt(10); tf.margin_right = Pt(10); tf.margin_bottom = Pt(8)
    first = True
    if heading:
        para(tf, [(heading, {"size": head_size, "bold": True, "color": accent})], space_after=5, first=True)
        first = False
    for ln in lines:
        if isinstance(ln, str):
            ln = [(ln, {})]
        para(tf, ln, size=line_size, color=TXT, space_after=4, first=first)
        first = False
    return box


def plot(s, path, left, top, max_w, max_h, pad=Inches(0.10)):
    """Painel branco + grafico encaixado dentro com padding."""
    panel = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, max_w, max_h)
    panel.fill.solid(); panel.fill.fore_color.rgb = BRANCO
    panel.line.color.rgb = BORDER; panel.line.width = Pt(1)
    panel.shadow.inherit = False
    if not os.path.exists(path):
        return
    inner_l = left + pad; inner_t = top + pad
    inner_w = max_w - 2 * pad; inner_h = max_h - 2 * pad
    try:
        from PIL import Image
        with Image.open(path) as im:
            iw, ih = im.size
        ar = iw / ih
        if ar > inner_w / inner_h:
            w = int(inner_w); h = int(inner_w / ar)
        else:
            h = int(inner_h); w = int(inner_h * ar)
        l = int(inner_l + (inner_w - w) // 2)
        t = int(inner_t + (inner_h - h) // 2)
        s.shapes.add_picture(path, l, t, width=w, height=h)
    except Exception:
        s.shapes.add_picture(path, inner_l, inner_t, width=inner_w)


def caption(s, text, top, left=Inches(0.65), width=Inches(12.03)):
    tb, tf = textbox(s, left, top, width, Inches(0.4), autoshrink=False)
    para(tf, [(text, {"size": 13, "color": MUT, "italic": True})], align=PP_ALIGN.CENTER, first=True)


def table(s, rows, left, top, width, height, col_w, hi_last=False, hi_col1_green=False,
          head_size=12.5, body_size=12):
    n, m = len(rows), len(rows[0])
    t = s.shapes.add_table(n, m, left, top, width, height).table
    for i, w in enumerate(col_w):
        t.columns[i].width = w
    for r in range(n):
        for c in range(m):
            cell = t.cell(r, c)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Pt(7); cell.margin_right = Pt(6)
            cell.margin_top = Pt(3); cell.margin_bottom = Pt(3)
            p = cell.text_frame.paragraphs[0]
            run = p.add_run(); run.text = rows[r][c]
            run.font.name = FONT
            run.font.size = Pt(round((head_size if r == 0 else body_size) * F * 2) / 2)
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = IFPR_ESCURO
                run.font.color.rgb = BRANCO; run.font.bold = True
            elif hi_last and r == n - 1:
                cell.fill.fore_color.rgb = ROW_HI
                run.font.bold = True; run.font.color.rgb = TXT
            else:
                cell.fill.fore_color.rgb = PANEL if r % 2 == 1 else PANEL_ALT
                run.font.color.rgb = TXT
            if hi_col1_green and r > 0 and c in (1, 2) and ("menor" in rows[r][c].lower() or "100%" in rows[r][c].lower() or "0,49" in rows[r][c] or "0,500" in rows[r][c] or "0,533" in rows[r][c]):
                run.font.color.rgb = VERDE; run.font.bold = True
    return t


# ================================================================== SLIDES

# 1 - CAPA
F = 1.0
s = slide()
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.22), SH)
bar.fill.solid(); bar.fill.fore_color.rgb = IFPR_VERDE; bar.line.fill.background(); bar.shadow.inherit = False

logo_path = os.path.join(IMG, "logo-ifpr.png")
if os.path.exists(logo_path):
    s.shapes.add_picture(logo_path, Inches(1.1), Inches(0.65), width=Inches(2.8))

tb, tf = textbox(s, Inches(1.1), Inches(1.65), Inches(11.3), Inches(5.2), MSO_ANCHOR.TOP, autoshrink=False)
para(tf, [("INSTITUTO FEDERAL DO PARANÁ · CAMPUS PINHAIS", {"size": 12, "color": IFPR_VERDE, "bold": True})], space_after=2, first=True)
para(tf, [("Bacharelado em Ciência da Computação", {"size": 13, "color": MUT})], space_after=18)
para(tf, [("Monitoramento de Funções", {"size": 36, "bold": True, "color": TXT})], space_after=0)
para(tf, [("Virtualizadas de Redes", {"size": 36, "bold": True, "color": TXT})], space_after=8)
para(tf, [("Um estudo comparativo entre ferramentas de extração de comportamento:\neBPF, Sysstat, Prometheus e API do Docker", {"size": 16, "color": MUT})], space_after=22)

rule_cov = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.15), Inches(4.95), Inches(2.2), Pt(4))
rule_cov.fill.solid(); rule_cov.fill.fore_color.rgb = IFPR_VERDE; rule_cov.line.fill.background()

tb_aut, tf_aut = textbox(s, Inches(1.1), Inches(5.2), Inches(11.3), Inches(1.8), MSO_ANCHOR.TOP, autoshrink=False)
para(tf_aut, [("Autores: ", {"size": 14, "color": MUT, "bold": True}),
              ("João Pedro dos Santos Henrique Plinta   ·   Rafael Correia Alves", {"size": 15, "color": TXT, "bold": True})], space_after=6, first=True)
para(tf_aut, [("Orientador: ", {"size": 14, "color": MUT, "bold": True}),
              ("Prof. Me. Guilherme Werneck de Oliveira", {"size": 14, "color": TXT})], space_after=16)
para(tf_aut, [("Defesa de Trabalho de Conclusão de Curso · Pinhais · 2026", {"size": 12, "color": IFPR_VERDE, "bold": True})])


# 2 - ROTEIRO
F = 1.2
s = slide(); header(s, "Visão geral", "Roteiro da apresentação", 2)
left_items = [
    "Contexto: NFV e o monitoramento de VNFs",
    "Problema, hipótese e objetivos",
    "As quatro abordagens comparadas",
    "Trabalhos relacionados e lacuna de pesquisa",
]
right_items = [
    "Metodologia e arquitetura experimental",
    "Resultados (480 execuções oficiais)",
    "Análise de sensibilidade da vazão (+480 execuções)",
    "Síntese, conclusões e trabalhos futuros",
]
tb, tf = textbox(s, Inches(0.65), Inches(1.85), Inches(5.9), Inches(3.6))
for i, t in enumerate(left_items, 1):
    para(tf, [(f"{i}.  ", {"size": 17, "color": IFPR_VERDE, "bold": True}), (t, {"size": 17})], space_after=14, first=(i == 1))
tb2, tf2 = textbox(s, Inches(6.85), Inches(1.85), Inches(5.9), Inches(3.6))
for i, t in enumerate(right_items, 5):
    para(tf2, [(f"{i}.  ", {"size": 17, "color": IFPR_VERDE, "bold": True}), (t, {"size": 17})], space_after=14, first=(i == 5))


# 3 - CONTEXTO NFV
F = 1.3
s = slide(); header(s, "Motivação", "Virtualização de Funções de Rede (NFV)", 3)
tb, tf = textbox(s, Inches(0.65), Inches(1.85), Inches(7.0), Inches(4.8))
for i, b in enumerate([
    [("A ", {}), ("NFV desacopla", {"bold": True, "color": VERDE}), (" funções de rede de hardwares proprietários e passam a rodar como software (", {}), ("VNFs", {"bold": True}), (") em servidores comuns.", {})],
    [("Exemplos de VNFs: firewall, IDS/IPS, balanceador de carga, UPF do 5G e ", {}), ("WAF", {"bold": True, "color": VERDE}), (" (Web Application Firewall).", {})],
    [("A elasticidade depende de ", {}), ("monitoramento contínuo", {"bold": True}), (": CPU, memória, vazão e latência.", {})],
    [("O ", {}), ("MANO", {"bold": True, "color": AZUL}), (" (Management and Orchestration, do ETSI) é a camada que gerencia o ciclo de vida das VNFs: usa essas métricas para decidir escalar, migrar ou recuperar uma VNF em tempo hábil.", {})],
]):
    para(tf, b, size=16.5, bullet=True, space_after=15, first=(i == 0))

card(s, Inches(7.95), Inches(1.90), Inches(4.73), Inches(4.3), VERDE, "O ponto-chave no ambiente NFV",
     [[("Métrica atrasada → orquestrador reage tarde → ", {}), ("violação de SLA", {"bold": True, "color": LARANJA}), (".", {})],
      [("", {})],
      [("O observador não é externo: roda ", {}), ("co-localizado à VNF", {"bold": True, "color": VERDE}), (", disputando os mesmos núcleos de CPU e memória do host.", {})],
      [("", {})],
      [("A literatura mostra que o monitoramento pode sobrecarregar a VNF.", {"italic": True, "color": MUT})]],
     line_size=13.5)


# 4 - PROBLEMA E HIPOTESE
F = 1.25
s = slide(); header(s, "Definição do problema", "Problema de pesquisa e hipótese", 4)
card(s, Inches(0.65), Inches(1.78), Inches(12.03), Inches(1.75), AZUL, "Questão de pesquisa",
     [[("A escolha da ferramenta impacta o gerenciamento e o ", {"size": 16}),
       ("tempo de tomada de decisão em redes vivas", {"size": 16, "bold": True}),
       (": quais são as diferenças práticas de desempenho entre ", {"size": 16}),
       ("eBPF, Sysstat, Prometheus e API do Docker", {"size": 16, "bold": True, "color": AZUL}),
       (" no monitoramento de uma VNF, e qual oferece ", {"size": 16}),
       ("menor sobrecarga", {"size": 16, "bold": True}), ("?", {"size": 16})]], head_size=18)

card(s, Inches(0.65), Inches(3.75), Inches(12.03), Inches(2.9), VERDE, "Hipótese",
     [[("O ", {}), ("eBPF", {"bold": True, "color": VERDE}), (", por operar em nível de ", {}), ("kernel", {"bold": True, "color": VERDE}),
       (" via kprobes, apresenta menor tempo de resposta e menor sobrecarga em comparação às abordagens em espaço de usuário:", {})],
      [("• ", {"bold": True}), ("Sysstat e Prometheus: ", {"bold": True}), ("polling via leitura e parsing de /proc;", {})],
      [("• ", {"bold": True}), ("API do Docker: ", {"bold": True}), ("consulta sob demanda aos cgroups intermediada pelo daemon dockerd.", {})]],
     line_size=17, head_size=18)


# 5 - OBJETIVOS
F = 1.3
s = slide(); header(s, "Metas do trabalho", "Objetivos", 5)
card(s, Inches(0.65), Inches(1.85), Inches(12.03), Inches(1.30), VERDE, "Objetivo Geral",
     [[("Compreender como as tecnologias ", {}),
       ("eBPF, Sysstat, Prometheus e API do Docker", {"bold": True, "color": VERDE}),
       (" influenciam, do ponto de vista do ", {}),
       ("tempo de resposta de extração", {"bold": True}), (" e da ", {}), ("sobrecarga", {"bold": True}),
       (", o monitoramento de uma VNF sob diferentes condições de consumo.", {})]], line_size=14.5)

tb, tf = textbox(s, Inches(0.65), Inches(3.40), Inches(12.03), Inches(3.3))
para(tf, [("Objetivos Específicos", {"size": 16, "bold": True, "color": AZUL})], space_after=10, first=True)
for b in [
    "Analisar os trabalhos da literatura que envolvem monitoramento no contexto de NFV;",
    "Implementar quatro coletores (eBPF, Sysstat, Prometheus e API do Docker) para monitorar um WAF;",
    "Executar experimentos quantitativos em quatro volumes de carga (100k, 500k, 1M e 2M), medindo tempo de resposta, CPU e memória;",
    "Compreender as vantagens, limitações e trade-offs operacionais de cada abordagem.",
]:
    para(tf, [(b, {"size": 15.5})], bullet=True, space_after=10)


# 6 - AS QUATRO ABORDAGENS
F = 1.2
s = slide(); header(s, "Tecnologias avaliadas", "As quatro abordagens comparadas", 6)
w_card = Inches(2.86)
gap = Inches(0.19)
left0 = Inches(0.65)

card(s, left0 + 0 * (w_card + gap), Inches(1.80), w_card, Inches(3.85), VERDE, "1. eBPF (CO-RE)",
     [[("Kernel-level", {"bold": True, "color": VERDE})],
      [("kprobes em tcp_sendmsg (TX) e tcp_cleanup_rbuf (RX), sport=8080.", {})],
      [("Acumula bytes em mapa BPF ARRAY no kernel; sem cópia de pacotes.", {})],
      [("Compilado sem BCC/LLVM em runtime (~15 MB RSS).", {"italic": True, "color": MUT})]], line_size=12.5)

card(s, left0 + 1 * (w_card + gap), Inches(1.80), w_card, Inches(3.85), AZUL, "2. Sysstat (/proc)",
     [[("User-space (polling)", {"bold": True, "color": AZUL})],
      [("Lê e faz parsing de /proc/net/dev (interface lo) a cada sonda.", {})],
      [("Consulta CPU e memória do WAF via psutil (/proc/<pid>).", {})],
      [("Abordagem leve, consolidada e sem privilégios de kernel.", {"italic": True, "color": MUT})]], line_size=12.5)

card(s, left0 + 2 * (w_card + gap), Inches(1.80), w_card, Inches(3.85), LARANJA, "3. Prometheus",
     [[("User-space + HTTP", {"bold": True, "color": LARANJA})],
      [("Mesma coleta do Sysstat (/proc/net/dev + psutil).", {})],
      [("Mantém servidor HTTP na porta :8000 expondo /metrics (Gauges).", {})],
      [("Avalia o custo de manter o exporter ativo em memória.", {"italic": True, "color": MUT})]], line_size=12.5)

card(s, left0 + 3 * (w_card + gap), Inches(1.80), w_card, Inches(3.85), ROXO, "4. API do Docker",
     [[("User-space → Daemon", {"bold": True, "color": ROXO})],
      [("SDK Python consulta stats(one_shot=True) via /var/run/docker.sock.", {})],
      [("O daemon dockerd lê cgroups v2 (CPU/memória) e serializa JSON.", {})],
      [("Dispensa pid:host, mas passa pelo IPC do daemon.", {"italic": True, "color": MUT})]], line_size=12.5)

card(s, Inches(0.65), Inches(5.85), Inches(12.03), Inches(0.88), VERDE, "",
     [[("Contraste arquitetural:  ", {"size": 14, "bold": True, "color": VERDE}),
       ("ler mapa em memória do kernel (eBPF)  vs.  parsing de /proc (Sysstat/Prometheus)  vs.  IPC HTTP/Unix + cgroups via daemon (Docker).", {"size": 14})]],
     bg_color=PANEL_ALT)


# 7 - TRABALHOS RELACIONADOS
F = 1.2
s = slide(); header(s, "Estado da arte", "Trabalhos relacionados e lacuna", 7)
rows = [
    ("Referência", "Foco / Tecnologias Analisadas", "Métricas de Sobrecarga", "Contexto / VNF"),
    ("Cassagnes et al. (2020)", "eBPF (kprobes) vs. polling em espaço de usuário", "Latência de instrumentação", "Rede geral / Host"),
    ("Casalicchio (2017) / Wiedner (2023)", "Medição em Docker e latência de cgroups v1/v2", "CPU, disco, latência de cauda", "Contêineres / NFV"),
    ("Dinga et al. (2023)", "ELK Stack, Netdata, Prometheus e Zipkin", "Consumo de energia, CPU, RAM", "Microsserviços em Docker"),
    ("Kannan (2024) / Shahinfar (2025)", "Agentes eBPF e isolamento sob concorrência", "CPU, memória, vazão, latência", "Kubernetes / Host"),
    ("Oliveira et al. (2026)", "Impacto da latência de coleta (Sysstat /proc)", "Latência de coleta, reação MANO", "NFV / DPI simulado"),
    ("Este trabalho (2026)", "eBPF + Sysstat + Prometheus + API do Docker", "RTT UDP, CPU e RAM (WAF e coletor)", "VNF (WAF isolado), 100k–2M"),
]
table(s, rows, Inches(0.65), Inches(1.80), Inches(12.03), Inches(3.85),
      [Inches(2.85), Inches(3.60), Inches(2.90), Inches(2.68)], hi_last=True, head_size=12, body_size=11.5)

tb, tf = textbox(s, Inches(0.65), Inches(5.80), Inches(12.03), Inches(0.95))
para(tf, [("Lacuna: ", {"size": 15, "bold": True, "color": LARANJA}),
          ("nenhum trabalho compara as ", {"size": 15}),
          ("quatro abordagens", {"size": 15, "bold": True, "color": VERDE}),
          (" sobre uma mesma VNF, com carga crescente e rigor estatístico. Este trabalho preenche essa lacuna.", {"size": 15})], first=True)


# 8 - METODOLOGIA E AMBIENTE
F = 1.25
s = slide(); header(s, "Como medimos", "Metodologia e ambiente experimental", 8)
tb, tf = textbox(s, Inches(0.65), Inches(1.85), Inches(6.8), Inches(4.8))
for i, b in enumerate([
    [("Classificação: ", {"bold": True}), ("pesquisa aplicada, quantitativa, comparativa e experimental.", {})],
    [("VNF avaliada: ", {"bold": True}), ("WAF em Python (asyncio + ThreadPoolExecutor) que inspeciona ", {}),
     ("SQLi, XSS, Path Traversal, RCE e Null Byte", {"bold": True, "color": VERDE}), (".", {})],
    [("Por concentrar carga intensiva de CPU na inspeção de conteúdo, o WAF torna visível qualquer sobrecarga imposta pelo observador.", {})],
    [("Isolamento: ", {"bold": True}), ("4 pilhas Docker Compose independentes; versões de bibliotecas fixadas nos Dockerfiles.", {})],
]):
    para(tf, b, size=15.5, bullet=True, space_after=14, first=(i == 0))

card(s, Inches(7.75), Inches(1.85), Inches(4.93), Inches(4.65), AZUL, "Ambiente Experimental (Host Dedicado)",
     [[("CPU: ", {"bold": True}), ("AMD Ryzen 5 5500 (6 cores / 12 threads, 4,27 GHz)", {})],
      [("RAM: ", {"bold": True}), ("16 GB DDR4", {})],
      [("SO: ", {"bold": True}), ("Ubuntu 26.04 LTS em ", {}), ("modo texto", {"bold": True, "color": VERDE}), (" (multi-user.target)", {})],
      [("Kernel: ", {"bold": True}), ("Linux 7.0.0-38-generic (com BTF)", {})],
      [("Docker Engine: ", {"bold": True}), ("29.8.2", {})],
      [("Stack eBPF: ", {"bold": True}), ("libbpf 1.3.0 + clang 18.1.3 (CO-RE)", {})],
      [("Bibliotecas: ", {"bold": True}), ("Python 3.12.3, psutil 7.2.2, prometheus_client 0.25.0, docker SDK 7.2.0", {})]],
     line_size=13)


# 9 - ARQUITETURA EXPERIMENTAL
F = 1.2
s = slide(); header(s, "Topologia", "Arquitetura experimental (Diagrama C4)", 9)
plot(s, os.path.join(IMG, "C4model.png"), Inches(0.65), Inches(1.78), Inches(7.45), Inches(4.85))
card(s, Inches(8.30), Inches(1.78), Inches(4.38), Inches(4.85), VERDE, "Fluxo de comunicação e medição",
     [[("1. Cliente (TCP :8080)", {"bold": True, "color": AZUL})],
      [("200 corrotinas asyncio com conexões persistentes; framing de 4 bytes big-endian.", {})],
      [("2. WAF (VNF)", {"bold": True, "color": VERDE})],
      [("Inspeciona cada payload (ALLOWED / BLOCKED) e grava waf_metrics.json atomicamente a cada 100 requisições.", {})],
      [("3. Observador (UDP :9999)", {"bold": True, "color": LARANJA})],
      [("Coleta métricas com a ferramenta em teste e responde às sondas com JSON.", {})],
      [("4. Probe (probe.py, 1 req/s)", {"bold": True, "color": ROXO})],
      [("Mede o RTT UDP com time.time_ns(), a métrica primária de sobrecarga.", {})]],
     line_size=12.5)


# 10 - PROTOCOLO DE TESTES
F = 1.2
s = slide(); header(s, "Desenho experimental", "Protocolo de testes e rigor estatístico", 10)
tb, tf = textbox(s, Inches(0.65), Inches(1.85), Inches(7.0), Inches(4.8))
for i, b in enumerate([
    [("Variável independente (N): ", {"bold": True}), ("100.000, 500.000, 1.000.000 e 2.000.000 mensagens.", {})],
    [("Cargas determinísticas: ", {"bold": True}), ("60% benignas + 40% maliciosas, pré-geradas com ", {}), ("seed=42", {"bold": True, "color": VERDE}), (" (sequência idêntica entre ferramentas).", {})],
    [("Janela de coleta: ", {"bold": True}), ("DURATION = ⌊N / 15000⌋ + 20 s (26, 53, 86 e 153 s): taxa nominal de 15 mil msg/s, mais 20 s de margem para subir e encerrar os contêineres.", {})],
    [("Repetições: ", {"bold": True}), ("30 execuções independentes por cenário → ", {}), ("480 execuções oficiais", {"bold": True, "color": VERDE}), (" (4 ferramentas × 4 volumes × 30).", {})],
    [("Validação e reprodutibilidade: ", {"bold": True}), ("escrita atômica em waf_metrics.json (0 falhas nas 480 execuções) + dashboard em ", {}), ("vnf-lab.up.railway.app", {"bold": True, "color": AZUL}), (".", {})],
]):
    para(tf, b, size=15, bullet=True, space_after=12, first=(i == 0))

card(s, Inches(7.90), Inches(1.85), Inches(4.78), Inches(4.75), VERDE, "Métricas e Análise Estatística",
     [[("Métrica Primária", {"bold": True, "color": VERDE})],
      [("• Tempo de resposta do observador (RTT UDP, em ms).", {})],
      [("Métricas Secundárias (Recursos)", {"bold": True, "color": AZUL})],
      [("• Memória e CPU do próprio observador;", {})],
      [("• CPU e memória do processo WAF (controle).", {})],
      [("Métricas de Validação", {"bold": True, "color": LARANJA})],
      [("• Tempo médio de inspeção (~0,080 ms) e contadores RX/TX.", {})],
      [("Critério Estatístico (t de Student, α = 0,05)", {"bold": True, "color": ROXO})],
      [("• IC95% = 2,045 × s / √30. Sem sobreposição de IC95% ⇒ diferença significativa.", {})]],
     line_size=12.5)


# 10b - DASHBOARD INTERATIVO (print em docs/imagens/dashboard.png; sem o arquivo, fica um quadro vazio)
F = 1.15
s = slide(); header(s, "Reprodutibilidade", "Dashboard interativo dos resultados")
plot(s, os.path.join(IMG, "dashboard.png"), Inches(0.65), Inches(1.78), Inches(7.9), Inches(4.85))
if not os.path.exists(os.path.join(IMG, "dashboard.png")):
    tbp, tfp = textbox(s, Inches(0.65), Inches(3.8), Inches(7.9), Inches(0.8), MSO_ANCHOR.MIDDLE, autoshrink=False)
    para(tfp, [("Cole aqui o print do dashboard (docs/imagens/dashboard.png)", {"size": 16, "color": MUT, "italic": True})],
         align=PP_ALIGN.CENTER, first=True)
card(s, Inches(8.75), Inches(1.78), Inches(3.93), Inches(4.85), VERDE, "Acesse e explore",
     [[("vnf-lab.up.railway.app", {"bold": True, "color": AZUL})],
      [("Acesso público, sem instalar nada.", {})]],
     line_size=14)
_qr = os.path.join(IMG, "qr_dashboard.png")
if os.path.exists(_qr):
    s.shapes.add_picture(_qr, Inches(9.35), Inches(3.55), width=Inches(2.75))
    tbq, tfq = textbox(s, Inches(8.75), Inches(6.2), Inches(3.93), Inches(0.35), autoshrink=False)
    para(tfq, [("Aponte a câmera do celular", {"size": 12, "color": MUT, "italic": True})], align=PP_ALIGN.CENTER, first=True)


# 11 - TEMPO DE RESPOSTA (RESULTADO PRINCIPAL)
F = 1.0
s = slide(); header(s, "Resultados · Métrica Primária", "Tempo de resposta (RTT UDP)", 11)
plot(s, os.path.join(IMG, "tempo_resposta_por_n.png"), Inches(0.65), Inches(1.75), Inches(5.75), Inches(3.70))

rows_rtt = [
    ("Volume (N)", "eBPF", "Sysstat", "Prometheus", "Docker"),
    ("100.000", "0,533 ± 0,003", "0,614 ± 0,005", "0,623 ± 0,004", "2,579 ± 0,011"),
    ("500.000", "0,496 ± 0,003", "0,571 ± 0,003", "0,583 ± 0,004", "2,503 ± 0,010"),
    ("1.000.000", "0,498 ± 0,002", "0,575 ± 0,004", "0,585 ± 0,003", "2,498 ± 0,011"),
    ("2.000.000", "0,500 ± 0,002", "0,573 ± 0,002", "0,584 ± 0,002", "2,506 ± 0,008"),
]
table(s, rows_rtt, Inches(6.55), Inches(1.75), Inches(6.13), Inches(2.15),
      [Inches(1.05), Inches(1.27), Inches(1.27), Inches(1.27), Inches(1.27)], hi_col1_green=True, head_size=12, body_size=11.5)

card(s, Inches(6.55), Inches(4.10), Inches(6.13), Inches(2.60), VERDE, "Principais achados (IC95% nunca se sobrepõem)",
     [[("• ", {"bold": True, "color": VERDE}), ("eBPF lidera em todos os volumes: ", {"bold": True}), ("−13% vs. Sysstat, −15% vs. Prometheus e −80% vs. Docker.", {})],
      [("• ", {"bold": True, "color": AZUL}), ("Por quê? ", {"bold": True}), ("Lê contadores prontos em mapa no kernel, sem parsear /proc.", {})],
      [("• ", {"bold": True, "color": ROXO}), ("Estável: ", {"bold": True}), ("a partir de 500k o RTT independe do volume.", {})]],
     line_size=15)
caption(s, "Valores em ms (média ± IC95%, n = 30). Menor é melhor.", Inches(5.55), left=Inches(0.65), width=Inches(5.75))


# 12 - DECOMPOSICAO DO CUSTO DO DOCKER + BOXPLOT
F = 1.0
s = slide(); header(s, "Resultados · Dispersão e Análise do Docker", "Distribuição do RTT e custo do Docker", 12)
plot(s, os.path.join(IMG, "boxplot_tempo_resposta.png"), Inches(0.65), Inches(1.75), Inches(7.75), Inches(4.85))

card(s, Inches(8.55), Inches(1.75), Inches(4.13), Inches(1.95), VERDE, "Distribuição (boxplot)",
     [[("• ", {}), ("eBPF sempre abaixo", {"bold": True, "color": VERDE}), (" de Sysstat e Prometheus.", {})],
      [("• Desvio-padrão de apenas ", {}), ("1% a 2% da média", {"bold": True}), (" nas 30 execuções.", {})]],
     line_size=15)

card(s, Inches(8.55), Inches(3.85), Inches(4.13), Inches(2.75), ROXO, "Por que o Docker leva ~2,5 ms?",
     [[("SDK → socket → daemon → cgroups → JSON, a cada sonda.", {"bold": True})],
      [("Análise isolada das etapas:", {"bold": True, "color": AZUL})],
      [("• Leitura direta do cgroup: ", {}), ("0,04–0,05 ms", {"bold": True, "color": VERDE})],
      [("• Chamada vazia (/_ping): ", {}), ("0,5–0,6 ms", {"bold": True})],
      [("• stats(one_shot): ", {}), ("1,4–1,7 ms (~30× mais)", {"bold": True, "color": ROXO})]],
     line_size=15)


# 13 - CPU DO WAF (CONTROLE)
F = 1.15
s = slide(); header(s, "Resultados · Variável de Controle", "Consumo de CPU do processo WAF", 13)
plot(s, os.path.join(IMG, "cpu_waf.png"), Inches(0.65), Inches(1.78), Inches(6.85), Inches(4.75))

card(s, Inches(7.70), Inches(1.78), Inches(4.98), Inches(4.75), AZUL, "Análise de interferência sobre a VNF",
     [[("• A partir de N = 500k, o WAF satura em ", {}), ("~104% a 110%", {"bold": True, "color": AZUL}), (" de um núcleo lógico em todos os cenários.", {})],
      [("• Em N = 1M: ", {"bold": True}), ("106,1% (eBPF), 105,3% (Sysstat), 105,3% (Prometheus) e 106,1% (Docker).", {})],
      [("• Tempo médio de inspeção por payload convergiu para ", {}), ("0,080 ms", {"bold": True, "color": VERDE}), (" nas 4 ferramentas.", {})],
      [("• ", {}), ("Conclusão de controle: ", {"bold": True, "color": VERDE}), ("nenhum coletor interfere de forma relevante na capacidade de processamento do WAF.", {})],
      [("• Ressalva metodológica: no Docker a CPU vem do cgroup (não do psutil), não sendo estritamente idêntica na fonte.", {"italic": True, "color": MUT})]],
     line_size=13)


# 14 - CPU DO OBSERVADOR (segue ordem do Cap. 3 do Overleaf: 3.3 CPU do Observador -> 3.4 Memoria)
F = 1.25
s = slide(); header(s, "Resultados · Sobrecarga do Coletor", "Consumo de CPU do próprio observador", 14)
rows_cpu_obs = [
    ("Volume (N)", "eBPF (%)", "Sysstat (%)", "Prometheus (%)", "Docker (%)"),
    ("100.000", "2,97 ± 5,97", "0,06 ± 0,01", "5,05 ± 7,09", "0,70 ± 1,19"),
    ("500.000", "0,05 ± 0,00", "2,50 ± 3,47", "0,06 ± 0,00", "0,79 ± 0,95"),
    ("1.000.000", "1,62 ± 2,25", "0,83 ± 1,59", "2,30 ± 3,39", "1,33 ± 0,92"),
    ("2.000.000", "0,56 ± 1,04", "0,93 ± 1,24", "0,92 ± 1,22", "0,21 ± 0,19"),
]
table(s, rows_cpu_obs, Inches(0.65), Inches(1.85), Inches(12.03), Inches(2.45),
      [Inches(2.43), Inches(2.4), Inches(2.4), Inches(2.4), Inches(2.4)], head_size=15, body_size=14.5)

card(s, Inches(0.65), Inches(4.55), Inches(12.03), Inches(2.20), AZUL, "Evidência qualitativa: inconclusiva do ponto de vista quantitativo",
     [[("• Médias de 0,05% a 5,05%, com ", {}), ("IC95% da ordem da própria média", {"bold": True, "color": LARANJA}), (" na maioria dos grupos.", {})],
      [("• Só 3 grupos ficaram baixos e estáveis (~0,05–0,06%): eBPF e Prometheus em 500k, Sysstat em 100k.", {})],
      [("• Causa: amostragem via psutil a cada 1 s e contenção de CPU entre contêineres.", {})],
      [("• No Docker, o cgroup é lido pelo ", {}), ("dockerd", {"bold": True, "color": ROXO}), (", fora do psutil do observador.", {})]],
     line_size=14)


# 15 - MEMORIA DO OBSERVADOR E DO WAF
F = 1.1
s = slide(); header(s, "Resultados · Sobrecarga de Memória", "Memória do observador e do WAF", 15)
plot(s, os.path.join(IMG, "memoria_observador.png"), Inches(0.65), Inches(1.78), Inches(6.85), Inches(4.75))

card(s, Inches(7.70), Inches(1.78), Inches(4.98), Inches(3.10), VERDE, "Memória do Observador (constante com N)",
     [[("• Sysstat: ", {"bold": True, "color": AZUL}), ("13,6 MB (menor consumo)", {"bold": True})],
      [("• eBPF: ", {"bold": True, "color": VERDE}), ("15,0 MB (−92% vs. ~196 MB do antigo BCC)", {})],
      [("• Prometheus: ", {"bold": True, "color": LARANJA}), ("24,7 MB (+81%, servidor HTTP)", {})],
      [("• Docker: ", {"bold": True, "color": ROXO}), ("30,8 MB (+126%, SDK docker)", {})]],
     line_size=13)

card(s, Inches(7.70), Inches(5.02), Inches(4.98), Inches(1.51), LARANJA, "Memória do WAF",
     [[("• RSS via psutil: de ", {}), ("~28 MB (100k) a ~46 MB (2M)", {"bold": True}), (", igual entre coletores.", {})],
      [("• Docker usa cgroup: grandeza distinta, não comparável.", {})]],
     line_size=12.5)


# 16 - ANALISE DE SENSIBILIDADE E COLETA 100%
F = 1.15
s = slide(); header(s, "Resultados · Investigação Adicional", "Sensibilidade da vazão (100% de N)", 16)
tb, tf = textbox(s, Inches(0.65), Inches(1.72), Inches(12.03), Inches(0.85), autoshrink=True)
para(tf, [("Gargalo: na coleta oficial o WAF (1 processo) não dá conta da vazão e inspeciona só 62% a 88% de N para N ≥ 500k. Multiplicamos os processos (proc.) e repetimos a bateria, com 30 repetições por ferramenta e volume (+480 execuções):", {"size": 14})], first=True)

rows_sens = [
    ("eBPF, N = 1M", "WAF", "Cliente", "Inspeções", "% de N"),
    ("Original (oficial, 30 rep.)", "1 proc.", "1 proc.", "706.407", "71%"),
    ("Cliente multiprocesso", "1 proc.", "4 proc.", "601.527", "60%"),
    ("WAF e cliente multiproc.", "4 proc.", "4 proc.", "650.067", "65%"),
    ("WAF e cliente 4 proc. + leitura direta", "4 proc.", "4 proc.", "1.000.000", "100%"),
]
table(s, rows_sens, Inches(0.65), Inches(2.70), Inches(5.45), Inches(2.55),
      [Inches(1.75), Inches(0.8), Inches(0.8), Inches(1.2), Inches(0.9)], hi_last=True, head_size=11, body_size=10.5)

rows_opt = [
    ("Volume (N)", "eBPF", "Sysstat", "Prometheus", "Docker"),
    ("100 mil", "0,533 → 0,900", "0,614 → 1,018", "0,622 → 1,031", "2,579 → 2,645"),
    ("500 mil", "0,496 → 0,903", "0,571 → 1,012", "0,583 → 1,035", "2,503 → 2,648"),
    ("1 milhão", "0,498 → 0,900", "0,575 → 1,014", "0,585 → 1,037", "2,498 → 2,658"),
    ("2 milhões", "0,500 → 0,902", "0,572 → 1,016", "0,584 → 1,037", "2,506 → 2,650"),
]
table(s, rows_opt, Inches(6.25), Inches(2.70), Inches(6.43), Inches(2.55),
      [Inches(1.0), Inches(1.36), Inches(1.36), Inches(1.36), Inches(1.35)], head_size=11, body_size=11)

card(s, Inches(0.65), Inches(5.45), Inches(12.03), Inches(1.40), VERDE, "Conclusão: 100% inspecionado, ordem preservada",
     [[("• ", {"bold": True, "color": VERDE}), ("eBPF (~0,90 ms) < Sysstat (~1,01) < Prometheus (~1,04) < Docker (~2,65), com IC95% estreito.", {})],
      [("• ", {"bold": True, "color": AZUL}), ("O aumento de ~0,4 ms vem do psutil consultar 4 processos waf.py por sonda; o Docker faz 1 chamada.", {})]],
     line_size=14)


# 17 - SINTESE DOS RESULTADOS
F = 1.0
s = slide(); header(s, "Visão consolidada", "Síntese comparativa das quatro abordagens", 17)
rows_sint = [
    ("Dimensão", "eBPF", "Sysstat", "Prometheus", "API do Docker"),
    ("Tempo de resposta (RTT)", "Menor (~0,50 ms)", "Intermediário (~0,57 ms)", "Intermediário (~0,58 ms)", "Maior (~2,50 ms)"),
    ("CPU do WAF", "Equivalente", "Equivalente", "Equivalente", "Equivalente (via cgroup)"),
    ("Memória do observador", "Baixa (~15,0 MB)", "Menor (~13,6 MB)", "Alta (~24,7 MB)", "Maior (~30,8 MB)"),
    ("CPU do observador", "Inconclusiva", "Inconclusiva (ruidosa)", "Inconclusiva (ruidosa)", "Inconclusiva (externa)"),
    ("Requisitos de privilégio", "Privilegiado + BTF + pid:host", "Não priv. + pid:host", "Não priv. + pid:host", "Socket docker.sock (sem pid:host)"),
]
table(s, rows_sint, Inches(0.65), Inches(1.80), Inches(12.03), Inches(2.95),
      [Inches(2.55), Inches(2.37), Inches(2.37), Inches(2.37), Inches(2.37)], hi_col1_green=True, head_size=13, body_size=12.5)

card(s, left0 + 0 * (w_card + gap), Inches(4.95), w_card, Inches(1.85), VERDE, "eBPF",
     [[("Menor RTT (−13% a −80%) e pouca memória. Exige privilégio de kernel.", {})]], line_size=14)
card(s, left0 + 1 * (w_card + gap), Inches(4.95), w_card, Inches(1.85), AZUL, "Sysstat",
     [[("Menor memória (~13,6 MB), simples e só ~0,07 ms atrás do eBPF.", {})]], line_size=14)
card(s, left0 + 2 * (w_card + gap), Inches(4.95), w_card, Inches(1.85), LARANJA, "Prometheus",
     [[("Paga ~11 MB de RAM pelo servidor HTTP; vale se integrado ao scraping.", {})]], line_size=14)
card(s, left0 + 3 * (w_card + gap), Inches(4.95), w_card, Inches(1.85), ROXO, "API do Docker",
     [[("Isola por contêiner, mas custa 5× mais RTT e ~31 MB de RAM.", {})]], line_size=14)


# 18 - CONCLUSOES
F = 1.3
s = slide(); header(s, "Fechamento", "Conclusões", 18)
tb, tf = textbox(s, Inches(0.65), Inches(1.85), Inches(12.03), Inches(4.9))
for i, b in enumerate([
    [("Hipótese confirmada na métrica primária: ", {"bold": True, "color": VERDE}),
     ("por operar no kernel, o eBPF obteve o menor tempo de resposta em todos os volumes (−13% vs. Sysstat, −15% vs. Prometheus e −80% vs. Docker), sem sobrecarregar o WAF.", {})],
    [("Ponderação prática (trade-off): ", {"bold": True, "color": AZUL}),
     ("o ganho sobre o polling de /proc é estatisticamente significativo, porém moderado em termos absolutos (0,07 a 0,09 ms), devendo ser pesado frente à maior complexidade do eBPF (C, compilação, privilégios).", {})],
    [("O custo das camadas de abstração: ", {"bold": True, "color": ROXO}),
     ("a API do Docker mostrou que o gargalo (~2,5 ms) não está no kernel (cgroup), mas no IPC via socket e serialização pelo daemon dockerd.", {})],
    [("Contribuições do trabalho: ", {"bold": True, "color": VERDE}),
     ("benchmark aberto e reprodutível com 960 execuções (480 oficiais + 480 de sensibilidade), migração BCC → libbpf CO-RE (−92% de RAM) e dashboard interativo público.", {})],
]):
    para(tf, b, size=16, bullet=True, space_after=16, first=(i == 0))


# 19 - LIMITACOES E TRABALHOS FUTUROS
F = 1.5
s = slide(); header(s, "Próximos passos", "Trabalhos futuros", 19)
card(s, Inches(0.65), Inches(1.85), Inches(12.03), Inches(4.85), VERDE, "",
     [[("• ", {"bold": True}), ("Leitura direta de cgroups v2: ", {"bold": True}), ("coletar de /sys/fs/cgroup/ sem passar pelo dockerd, para isolar o custo da API do Docker (~2,5 ms).", {})],
      [("• ", {"bold": True}), ("Ambiente de produção: ", {"bold": True}), ("repetir o experimento em rede física e com o volume de pacotes de produção, não só em loopback.", {})],
      [("• ", {"bold": True}), ("Impacto fim a fim na VNF: ", {"bold": True}), ("medir como o monitoramento afeta a latência e a vazão das requisições dos clientes do WAF.", {})],
      [("• ", {"bold": True}), ("WAF de alta vazão em processo único: ", {"bold": True}), ("atingir 100% de N sem multiplicar os processos monitorados pelo psutil.", {})],
      [("• ", {"bold": True}), ("Novos cenários: ", {"bold": True}), ("cadeias SFC completas, Prometheus com scraping ativo e hooks XDP/TC no eBPF.", {})]],
     line_size=14)


# 20 - ENCERRAMENTO
F = 1.0
s = slide()
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.22), SH)
bar.fill.solid(); bar.fill.fore_color.rgb = IFPR_VERDE; bar.line.fill.background(); bar.shadow.inherit = False

if os.path.exists(logo_path):
    s.shapes.add_picture(logo_path, Inches(1.1), Inches(0.75), width=Inches(2.8))

tb, tf = textbox(s, Inches(1.1), Inches(2.0), Inches(6.3), Inches(4.8), MSO_ANCHOR.TOP, autoshrink=False)
para(tf, [("Obrigado!", {"size": 48, "bold": True, "color": TXT})], space_after=8, first=True)
para(tf, [("Dúvidas e considerações da banca", {"size": 22, "color": MUT})], space_after=28)
para(tf, [("João Pedro dos Santos Henrique Plinta", {"size": 18, "color": TXT, "bold": True})], space_after=2)
para(tf, [("Rafael Correia Alves", {"size": 18, "color": TXT, "bold": True})], space_after=10)
para(tf, [("Orientador: Prof. Me. Guilherme Werneck de Oliveira", {"size": 15, "color": MUT})], space_after=0)


def qr_card(left, img_name, titulo, url_txt, cor):
    top = Inches(1.9)
    w, h = Inches(2.65), Inches(3.95)
    box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, w, h)
    box.fill.solid(); box.fill.fore_color.rgb = PANEL
    box.line.color.rgb = BORDER; box.line.width = Pt(1); box.shadow.inherit = False
    strip = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, w, Inches(0.08))
    strip.fill.solid(); strip.fill.fore_color.rgb = cor; strip.line.fill.background(); strip.shadow.inherit = False
    qr = os.path.join(IMG, img_name)
    if os.path.exists(qr):
        s.shapes.add_picture(qr, left + Inches(0.2), top + Inches(0.3), width=Inches(2.25))
    tbq, tfq = textbox(s, left, top + Inches(2.62), w, Inches(1.25), autoshrink=False)
    para(tfq, [(titulo, {"size": 15, "bold": True, "color": cor})], align=PP_ALIGN.CENTER, space_after=2, first=True)
    para(tfq, [(url_txt, {"size": 10.5, "color": MUT})], align=PP_ALIGN.CENTER, space_after=0)


qr_card(Inches(7.75), "qr_repo.png", "Código-fonte e dados", "github.com/joaopedroplinta/\nvnf-monitoring-benchmark", IFPR_VERDE)
qr_card(Inches(10.55), "qr_dashboard.png", "Dashboard interativo", "vnf-lab.up.railway.app", AZUL)

prs.save(OUT)
print("OK ->", OUT)
print("Slides:", len(prs.slides._sldIdLst))
