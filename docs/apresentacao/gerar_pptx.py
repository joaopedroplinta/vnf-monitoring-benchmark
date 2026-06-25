#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a apresentacao da pre-banca do TCC em PPTX editavel — tema ESCURO tech/moderno.
Caixas de texto, tabelas e formas nativas (editaveis no PowerPoint/Canva).
Reaproveita os graficos em docs/imagens/.

Decisoes anti-sobreposicao:
  - Fonte Arial (existe no Canva; evita substituicao por fonte mais larga).
  - auto_size = TEXT_TO_FIT_SHAPE nas caixas/cards (texto encolhe se faltar espaco).
  - Coordenadas com folga; graficos sobre painel branco com padding.

Uso:  python gerar_pptx.py
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

# ---- paleta escura (GitHub dark + neon) ----
BG      = RGBColor(0x0D, 0x11, 0x17)   # fundo grafite
PANEL   = RGBColor(0x16, 0x1B, 0x22)   # cartao
BORDER  = RGBColor(0x30, 0x36, 0x3D)   # borda sutil
TXT     = RGBColor(0xE6, 0xED, 0xF3)   # texto claro
MUT     = RGBColor(0x8B, 0x94, 0x9E)   # texto secundario
VERDE   = RGBColor(0x3F, 0xB9, 0x50)   # eBPF (neon)
AZUL    = RGBColor(0x58, 0xA6, 0xFF)   # Sysstat / acento
LARANJA = RGBColor(0xD2, 0x99, 0x22)   # Prometheus
BRANCO  = RGBColor(0xFF, 0xFF, 0xFF)
ROW_HI  = RGBColor(0x10, 0x2A, 0x16)   # destaque verde escuro p/ linha de tabela

# ---- 16:9 ----
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]


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
        r.font.size = Pt(kw.get("size", size))
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


def para(tf, runs, size=18, color=TXT, bold=False, italic=False, align=PP_ALIGN.LEFT,
         space_after=6, bullet=False, first=False, accent=VERDE):
    p = tf.paragraphs[0] if (first and not tf.paragraphs[0].runs) else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    if bullet:
        # bolinha colorida como prefixo (mais confiavel que buChar no Canva)
        r = p.add_run(); r.text = "▸  "
        r.font.size = Pt(size); r.font.color.rgb = accent; r.font.name = FONT; r.font.bold = True
    _runs(p, runs, size, color, bold, italic)
    return p


def header(s, kicker, ttl, num):
    # kicker pequeno em maiusculas
    tb, tf = textbox(s, Inches(0.65), Inches(0.45), Inches(11.5), Inches(0.35), autoshrink=False)
    para(tf, [(kicker.upper(), {"size": 12, "color": AZUL, "bold": True})], first=True)
    # titulo grande
    tb2, tf2 = textbox(s, Inches(0.6), Inches(0.78), Inches(12.1), Inches(0.95), autoshrink=True)
    para(tf2, [(ttl, {"size": 28, "color": TXT, "bold": True})], first=True)
    # regra de acento
    rule = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(1.62), Inches(1.3), Pt(3))
    rule.fill.solid(); rule.fill.fore_color.rgb = VERDE; rule.line.fill.background()
    # numero do slide
    tb3, tf3 = textbox(s, Inches(12.3), Inches(7.02), Inches(0.85), Inches(0.35), autoshrink=False)
    para(tf3, [(f"{num:02d}", {"size": 11, "color": MUT})], align=PP_ALIGN.RIGHT, first=True)
    # marca rodape esquerda
    tb4, tf4 = textbox(s, Inches(0.65), Inches(7.02), Inches(7), Inches(0.35), autoshrink=False)
    para(tf4, [("Pré-banca TCC · IFPR Pinhais", {"size": 10, "color": MUT})], first=True)


def card(s, left, top, width, height, accent, heading, lines, head_size=16, line_size=13):
    box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    box.fill.solid(); box.fill.fore_color.rgb = PANEL
    box.line.color.rgb = BORDER; box.line.width = Pt(0.75)
    box.shadow.inherit = False
    # barra de acento a esquerda (dentro do card, sem estourar)
    strip = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, Inches(0.07), height)
    strip.fill.solid(); strip.fill.fore_color.rgb = accent; strip.line.fill.background()
    strip.shadow.inherit = False
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Pt(14); tf.margin_top = Pt(10); tf.margin_right = Pt(10); tf.margin_bottom = Pt(8)
    first = True
    if heading:
        para(tf, [(heading, {"size": head_size, "bold": True, "color": accent})], space_after=6, first=True)
        first = False
    for ln in lines:
        if isinstance(ln, str):
            ln = [(ln, {})]
        para(tf, ln, size=line_size, color=TXT, space_after=5, first=first)
        first = False
    return box


def plot(s, path, left, top, max_w, max_h, pad=Inches(0.12)):
    """Painel branco arredondado + grafico encaixado dentro com padding."""
    panel = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, max_w, max_h)
    panel.fill.solid(); panel.fill.fore_color.rgb = BRANCO
    panel.line.color.rgb = BORDER; panel.line.width = Pt(0.75)
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
            w = inner_w; h = int(inner_w / ar)
        else:
            h = inner_h; w = int(inner_h * ar)
        l = inner_l + (inner_w - w) // 2
        t = inner_t + (inner_h - h) // 2
        s.shapes.add_picture(path, l, t, width=w, height=h)
    except Exception:
        s.shapes.add_picture(path, inner_l, inner_t, width=inner_w)


def caption(s, text, top, left=Inches(0.6), width=Inches(12.1)):
    tb, tf = textbox(s, left, top, width, Inches(0.45), autoshrink=False)
    para(tf, [(text, {"size": 12, "color": MUT, "italic": True})], align=PP_ALIGN.CENTER, first=True)


def table(s, rows, left, top, width, height, col_w, hi_last=False, hi_col1_green=False,
          head_size=13, body_size=13):
    n, m = len(rows), len(rows[0])
    t = s.shapes.add_table(n, m, left, top, width, height).table
    # remover estilo padrao (banding) deixando minimalista
    for i, w in enumerate(col_w):
        t.columns[i].width = w
    for r in range(n):
        for c in range(m):
            cell = t.cell(r, c)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Pt(8); cell.margin_right = Pt(6)
            cell.margin_top = Pt(3); cell.margin_bottom = Pt(3)
            p = cell.text_frame.paragraphs[0]
            run = p.add_run(); run.text = rows[r][c]
            run.font.name = FONT
            run.font.size = Pt(head_size if r == 0 else body_size)
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = RGBColor(0x1F, 0x6F, 0xEB)
                run.font.color.rgb = BRANCO; run.font.bold = True
            elif hi_last and r == n - 1:
                cell.fill.fore_color.rgb = ROW_HI
                run.font.bold = True; run.font.color.rgb = TXT
            else:
                cell.fill.fore_color.rgb = PANEL
                run.font.color.rgb = TXT
            if hi_col1_green and r > 0 and c == 1 and ("menor" in rows[r][c].lower()):
                run.font.color.rgb = VERDE; run.font.bold = True
            if hi_col1_green and r > 0 and c == 2 and ("menor" in rows[r][c].lower()):
                run.font.color.rgb = VERDE; run.font.bold = True
    return t


# ================================================================== SLIDES

# 1 - CAPA
s = slide()
# faixa de acento vertical a esquerda
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), SH)
bar.fill.solid(); bar.fill.fore_color.rgb = VERDE; bar.line.fill.background(); bar.shadow.inherit = False
tb, tf = textbox(s, Inches(1.1), Inches(0.0), Inches(11.2), SH, MSO_ANCHOR.MIDDLE, autoshrink=False)
para(tf, [("INSTITUTO FEDERAL DO PARANÁ · CAMPUS PINHAIS", {"size": 13, "color": AZUL, "bold": True})], space_after=4, first=True)
para(tf, [("Bacharelado em Ciência da Computação", {"size": 13, "color": MUT})], space_after=22)
para(tf, [("Monitoramento de Funções", {"size": 40, "bold": True, "color": TXT})], space_after=0)
para(tf, [("Virtualizadas de Redes", {"size": 40, "bold": True, "color": TXT})], space_after=10)
para(tf, [("Um estudo comparativo entre ferramentas de extração de comportamento", {"size": 17, "color": MUT})], space_after=26)
para(tf, [("Rafael Correia Alves   ·   João Pedro dos Santos Henrique Plinta", {"size": 15, "color": TXT})], space_after=4)
para(tf, [("Orientador: Prof. Guilherme Werneck de Oliveira", {"size": 13, "color": MUT})], space_after=18)
para(tf, [("Pré-banca · Pinhais · 2026", {"size": 12, "color": VERDE, "bold": True})])

# 2 - ROTEIRO
s = slide(); header(s, "Visão geral", "Roteiro da apresentação", 2)
left_items = ["Contexto: NFV e o monitoramento de VNFs",
              "Problema, hipótese e objetivos",
              "As três abordagens comparadas",
              "Lacuna na literatura"]
right_items = ["Metodologia e arquitetura experimental",
               "Resultados (360 execuções)",
               "Síntese e conclusões",
               "Limitações e trabalhos futuros"]
tb, tf = textbox(s, Inches(0.65), Inches(1.95), Inches(6.0), Inches(3.7))
for i, t in enumerate(left_items, 1):
    para(tf, [(f"{i}.  ", {"size": 18, "color": VERDE, "bold": True}), (t, {"size": 18})], space_after=14, first=(i == 1))
tb2, tf2 = textbox(s, Inches(6.95), Inches(1.95), Inches(6.0), Inches(3.7))
for i, t in enumerate(right_items, 5):
    para(tf2, [(f"{i}.  ", {"size": 18, "color": VERDE, "bold": True}), (t, {"size": 18})], space_after=14, first=(i == 5))
card(s, Inches(0.65), Inches(5.75), Inches(12.05), Inches(0.95), AZUL, "",
     [[("Pergunta central:  ", {"size": 15, "bold": True, "color": AZUL}),
       ("monitorar uma VNF tem um custo — qual ferramenta cobra menos por isso?", {"size": 15})]])

# 3 - CONTEXTO NFV
s = slide(); header(s, "Motivação", "Virtualização de Funções de Rede (NFV)", 3)
tb, tf = textbox(s, Inches(0.65), Inches(1.95), Inches(7.0), Inches(4.8))
for i, b in enumerate([
    [("NFV ", {}), ("desacopla", {"bold": True, "color": VERDE}), (" funções de rede do hardware — viram software (VNFs) em servidores comuns.", {})],
    [("Exemplos de VNF: firewall, IDS, balanceador, ", {}), ("WAF", {"bold": True, "color": VERDE}), (".", {})],
    [("Flexibilidade exige ", {}), ("monitoramento constante", {"bold": True}), (": CPU, memória, tráfego, latência.", {})],
    [("O orquestrador (MANO) decide escalar ou recuperar a VNF a partir dessas métricas.", {})],
]):
    para(tf, b, size=17, bullet=True, space_after=16, first=(i == 0))
card(s, Inches(8.0), Inches(2.05), Inches(4.7), Inches(3.6), VERDE, "O ponto-chave",
     [[("Métrica atrasada → orquestrador reage tarde → violação de SLA.", {})],
      [("", {})],
      [("O monitor roda ", {}), ("co-localizado", {"bold": True, "color": VERDE}), (" à VNF: disputa os mesmos núcleos de CPU e memória.", {})]],
     line_size=14)

# 4 - PROBLEMA
s = slide(); header(s, "Definição do problema", "Problema, hipótese e lacuna", 4)
tb, tf = textbox(s, Inches(0.65), Inches(1.9), Inches(12.05), Inches(0.95))
para(tf, [("A própria ferramenta de monitoramento ", {"size": 17}), ("consome recursos", {"size": 17, "bold": True, "color": LARANJA}),
          (" que deveriam ir para a VNF — um coletor pesado degrada o serviço que deveria só observar.", {"size": 17})], first=True)
card(s, Inches(0.65), Inches(2.95), Inches(12.05), Inches(1.05), AZUL, "",
     [[("Pergunta de pesquisa:  ", {"size": 15, "bold": True, "color": AZUL}),
       ("quais as diferenças de desempenho entre eBPF, Sysstat e Prometheus ao monitorar uma VNF, e qual impõe menor sobrecarga?", {"size": 15})]])
card(s, Inches(0.65), Inches(4.2), Inches(5.85), Inches(2.45), VERDE, "Hipótese",
     [[("O eBPF, por operar no ", {}), ("kernel", {"bold": True, "color": VERDE}),
       (", deve ter o menor tempo de resposta e impacto, frente ao polling em espaço de usuário (Sysstat e Prometheus via /proc).", {})]], line_size=14)
card(s, Inches(6.85), Inches(4.2), Inches(5.85), Inches(2.45), LARANJA, "Lacuna na literatura",
     [[("Faltam estudos ", {}), ("quantitativos controlados", {"bold": True, "color": LARANJA}),
       (" comparando as três abordagens sobre uma mesma VNF, em condições equivalentes.", {})]], line_size=14)

# 5 - OBJETIVOS
s = slide(); header(s, "Metas do trabalho", "Objetivos", 5)
card(s, Inches(0.65), Inches(1.95), Inches(12.05), Inches(1.35), VERDE, "Objetivo geral",
     [[("Compreender como eBPF, Sysstat e Prometheus influenciam, em ", {}),
       ("tempo de resposta", {"bold": True}), (" e ", {}), ("sobrecarga", {"bold": True}),
       (", o monitoramento de uma VNF sob diferentes cargas.", {})]], line_size=15)
tb, tf = textbox(s, Inches(0.65), Inches(3.55), Inches(12.05), Inches(3.0))
para(tf, [("Objetivos específicos", {"size": 16, "bold": True, "color": AZUL})], space_after=12, first=True)
for b in [
    "Levantar a literatura de monitoramento em NFV;",
    "Implementar três coletores (eBPF, Sysstat, Prometheus) para um WAF;",
    "Executar experimentos com 4 cargas distintas, medindo tempo de extração, CPU e memória;",
    "Compreender vantagens e limitações de cada abordagem.",
]:
    para(tf, [(b, {"size": 17})], bullet=True, space_after=12)

# 6 - AS TRES FERRAMENTAS
s = slide(); header(s, "Tecnologias avaliadas", "As três abordagens comparadas", 6)
card(s, Inches(0.65), Inches(1.95), Inches(3.85), Inches(3.7), VERDE, "eBPF",
     [[("Kernel-level", {"bold": True, "color": VERDE})],
      [("kprobes em tcp_sendmsg e tcp_cleanup_rbuf.", {})],
      [("Conta bytes no kernel via mapas BPF; usuário só lê o agregado.", {})],
      [("libbpf + CO-RE, sem cópia de pacotes.", {"italic": True, "color": MUT})]], line_size=13)
card(s, Inches(4.74), Inches(1.95), Inches(3.85), Inches(3.7), AZUL, "Sysstat",
     [[("User-space", {"bold": True, "color": AZUL})],
      [("Polling de /proc/net/dev + psutil a cada requisição.", {})],
      [("Lê e faz parsing de arquivos de texto do /proc.", {})],
      [("Consolidada e portável.", {"italic": True, "color": MUT})]], line_size=13)
card(s, Inches(8.83), Inches(1.95), Inches(3.87), Inches(3.7), LARANJA, "Prometheus",
     [[("User-space", {"bold": True, "color": LARANJA})],
      [("Mesma lógica do Sysstat + servidor HTTP na porta 8000.", {})],
      [("Expõe /metrics no padrão Prometheus.", {})],
      [("Padrão em microsserviços.", {"italic": True, "color": MUT})]], line_size=13)
card(s, Inches(0.65), Inches(5.85), Inches(12.05), Inches(0.85), VERDE, "",
     [[("Contraste central:  ", {"size": 15, "bold": True, "color": VERDE}),
       ("ler contadores no kernel  vs.  fazer polling de /proc no espaço de usuário.", {"size": 15})]])

# 7 - TRABALHOS RELACIONADOS
s = slide(); header(s, "Estado da arte", "Lacuna na literatura", 7)
rows = [
    ("Trabalho", "Tecnologias", "Comparou as 3?", "Carga / VNF"),
    ("Cassagnes et al. (2020)", "eBPF vs. polling", "Não (sem Prometheus)", "Rede geral"),
    ("Sathyaseelan et al. (2024)", "eBPF", "Não", "Kubernetes"),
    ("Shahinfar et al. (2025)", "eBPF", "Não", "Host / rede"),
    ("Oliveira et al. (2026)", "Sysstat", "Não", "DPI simulado"),
    ("Este trabalho", "eBPF + Sysstat + Prometheus", "Sim", "WAF, 100k–2M msgs"),
]
table(s, rows, Inches(0.65), Inches(1.95), Inches(12.05), Inches(3.3),
      [Inches(3.2), Inches(3.6), Inches(2.85), Inches(2.4)], hi_last=True)
tb, tf = textbox(s, Inches(0.65), Inches(5.5), Inches(12.05), Inches(1.1))
para(tf, [("Nenhum estudo compara ", {"size": 16}), ("as três", {"size": 16, "bold": True, "color": VERDE}),
          (" abordagens sobre uma mesma VNF, com cargas crescentes e controladas. É essa lacuna que preenchemos.", {"size": 16})], first=True)

# 8 - METODOLOGIA
s = slide(); header(s, "Como medimos", "Metodologia", 8)
tb, tf = textbox(s, Inches(0.65), Inches(1.95), Inches(7.1), Inches(4.6))
for i, b in enumerate([
    [("Pesquisa ", {}), ("aplicada, quantitativa, comparativa e experimental", {"bold": True}), (".", {})],
    [("VNF representativa: um ", {}), ("WAF", {"bold": True, "color": VERDE}), (" que inspeciona SQLi, XSS, Path Traversal, RCE e Null Byte.", {})],
    [("WAF é intensivo em CPU → torna ", {}), ("visível", {"bold": True}), (" qualquer sobrecarga do coletor.", {})],
]):
    para(tf, b, size=17, bullet=True, space_after=16, first=(i == 0))
card(s, Inches(8.05), Inches(2.05), Inches(4.65), Inches(3.6), AZUL, "Ambiente de testes",
     [[("AMD Ryzen 5 5500 (6c / 12t)", {})],
      [("16 GB RAM · Ubuntu 26.04 LTS", {})],
      [("kernel 7.0.0-15-generic", {})],
      [("3 pilhas Docker Compose isoladas", {})],
      [("libbpf 1.3 · clang 18 · Python 3.12", {})]], line_size=14)

# 9 - ARQUITETURA
s = slide(); header(s, "Topologia", "Arquitetura experimental", 9)
plot(s, os.path.join(IMG, "C4model.drawio.png"), Inches(1.5), Inches(1.95), Inches(10.3), Inches(4.35))
caption(s, "Cliente → WAF (TCP 8080) → Observador (UDP 9999);  probe.py mede o RTT a cada 1 s.", Inches(6.45))

# 10 - PROTOCOLO
s = slide(); header(s, "Desenho experimental", "Protocolo de testes", 10)
tb, tf = textbox(s, Inches(0.65), Inches(1.95), Inches(7.1), Inches(4.6))
for i, b in enumerate([
    [("Variável independente: ", {"bold": True}), ("N = 100k, 500k, 1M, 2M mensagens.", {})],
    [("Carga 60% benigna + 40% maliciosa, semente fixa → ", {}), ("idêntica", {"bold": True, "color": VERDE}), (" entre ferramentas.", {})],
    [("Cliente: 200 corrotinas assíncronas, conexões TCP persistentes.", {})],
    [("30 repetições por combinação → ", {}), ("360 execuções.", {"bold": True, "color": VERDE})],
]):
    para(tf, b, size=17, bullet=True, space_after=15, first=(i == 0))
card(s, Inches(8.05), Inches(2.05), Inches(4.65), Inches(4.3), VERDE, "Métricas",
     [[("Primária", {"bold": True, "color": VERDE})],
      [("Tempo de resposta do observador (RTT UDP), em ns, via probe.py.", {})],
      [("", {})],
      [("Secundárias", {"bold": True, "color": AZUL})],
      [("CPU e memória do WAF e do próprio coletor.", {})],
      [("", {})],
      [("Agregação: média ± IC95% (t de Student, n=30).", {"italic": True, "color": MUT})]], line_size=13)

# 11 - TEMPO DE RESPOSTA (principal)
s = slide(); header(s, "Resultado · métrica primária", "Tempo de resposta do observador", 11)
plot(s, os.path.join(IMG, "tempo_resposta_por_n.png"), Inches(0.6), Inches(1.95), Inches(7.3), Inches(4.55))
tb, tf = textbox(s, Inches(8.15), Inches(1.95), Inches(4.6), Inches(4.6))
para(tf, [("−8% a −15%", {"size": 32, "bold": True, "color": VERDE})], space_after=8, first=True)
para(tf, [("O eBPF teve o menor RTT em ", {"size": 16}), ("todos", {"size": 16, "bold": True}), (" os volumes.", {"size": 16})], space_after=12)
for b in [
    [("8,1% a 14,7% menor vs. Sysstat.", {})],
    [("10,9% a 14,0% menor vs. Prometheus.", {})],
    [("IC95% ", {}), ("nunca se sobrepõem", {"bold": True, "color": VERDE}), (" → estatisticamente significativo.", {})],
]:
    para(tf, b, size=15, bullet=True, space_after=10)

# 12 - BOXPLOT
s = slide(); header(s, "Resultado · dispersão", "Distribuição do tempo de resposta", 12)
plot(s, os.path.join(IMG, "boxplot_tempo_resposta.png"), Inches(1.3), Inches(1.95), Inches(10.7), Inches(4.0))
tb, tf = textbox(s, Inches(0.65), Inches(6.05), Inches(12.05), Inches(0.95), autoshrink=False)
para(tf, [("Em 500k e 1M a caixa do eBPF fica ", {"size": 14}), ("toda abaixo", {"size": 14, "bold": True, "color": VERDE}),
          (" das demais. Contrapartida: maior dispersão e outliers (máx. 1,06 ms em 2M).", {"size": 14})], first=True)

# 13 - CPU WAF
s = slide(); header(s, "Resultado · controle", "Consumo de CPU do WAF", 13)
plot(s, os.path.join(IMG, "cpu_waf.png"), Inches(0.6), Inches(1.95), Inches(7.3), Inches(4.55))
tb, tf = textbox(s, Inches(8.15), Inches(2.1), Inches(4.6), Inches(4.4))
for i, b in enumerate([
    [("A partir de 500k o WAF satura em ", {}), ("~107–109%", {"bold": True, "color": AZUL}), (" de uma thread.", {})],
    [("Igual nos três casos", {"bold": True}), (" (IC95% sobrepostos).", {})],
    [("Confirma: nenhum coletor interfere no caminho de inspeção do WAF.", {})],
    [("O coletor afeta sua própria sobrecarga, não a CPU da VNF.", {"italic": True, "color": MUT})],
]):
    para(tf, b, size=16, space_after=14, first=(i == 0))

# 14 - MEMORIA OBSERVADOR
s = slide(); header(s, "Resultado · sobrecarga", "Memória do observador", 14)
plot(s, os.path.join(IMG, "memoria_observador.png"), Inches(0.6), Inches(1.95), Inches(7.3), Inches(4.55))
tb, tf = textbox(s, Inches(8.15), Inches(2.1), Inches(4.6), Inches(4.4))
para(tf, [("Maior separação entre as três:", {"size": 16})], space_after=12, first=True)
para(tf, [("Sysstat", {"size": 16, "bold": True, "color": AZUL}), ("  ~14 MB (menor)", {"size": 16})], bullet=True, space_after=10, accent=AZUL)
para(tf, [("eBPF", {"size": 16, "bold": True, "color": VERDE}), ("  ~15 MB", {"size": 16})], bullet=True, space_after=10, accent=VERDE)
para(tf, [("Prometheus", {"size": 16, "bold": True, "color": LARANJA}), ("  ~24 MB (+78%)", {"size": 16})], bullet=True, space_after=14, accent=LARANJA)
para(tf, [("Custo do servidor HTTP + prometheus_client. Constante com o volume.", {"size": 13, "italic": True, "color": MUT})])

# 15 - CPU OBSERVADOR
s = slide(); header(s, "Resultado · sobrecarga", "CPU do próprio observador", 15)
tb, tf = textbox(s, Inches(0.65), Inches(1.95), Inches(12.05), Inches(0.6), autoshrink=False)
para(tf, [("Resultado mais limpo em N = 100k:", {"size": 18})], first=True)
rows = [("Coletor", "CPU média do observador"),
        ("eBPF", "0,05% ± 0,01  (menor)"),
        ("Prometheus", "2,37%"),
        ("Sysstat", "4,66%")]
table(s, rows, Inches(2.8), Inches(2.65), Inches(7.7), Inches(2.4),
      [Inches(3.2), Inches(4.5)], head_size=15, body_size=16, hi_col1_green=True)
tb, tf = textbox(s, Inches(0.65), Inches(5.35), Inches(12.05), Inches(1.5))
para(tf, [("eBPF consome CPU ", {"size": 17}), ("1 a 2 ordens de grandeza menor", {"size": 17, "bold": True, "color": VERDE}),
          (" — ler mapas do kernel é muito mais barato que parsear /proc.", {"size": 17})], space_after=8, first=True)
para(tf, [("Em volumes maiores a métrica fica ruidosa (psutil + contenção de CPU) → evidência qualitativa.", {"size": 13, "italic": True, "color": MUT})])

# 16 - SINTESE
s = slide(); header(s, "Visão consolidada", "Síntese dos resultados", 16)
rows = [
    ("Dimensão", "eBPF", "Sysstat", "Prometheus"),
    ("Tempo de resposta (RTT)", "Menor", "Intermediário", "Maior"),
    ("CPU do WAF", "Equivalente", "Equivalente", "Equivalente"),
    ("Memória do observador", "~15 MB", "~14 MB (menor)", "~24 MB (maior)"),
    ("CPU do observador", "Menor / estável", "Maior / ruidosa", "Maior / ruidosa"),
]
table(s, rows, Inches(0.65), Inches(1.95), Inches(12.05), Inches(2.7),
      [Inches(3.65), Inches(2.8), Inches(2.8), Inches(2.8)], hi_col1_green=True, body_size=13)
card(s, Inches(0.65), Inches(4.95), Inches(3.85), Inches(1.75), VERDE, "eBPF",
     [[("Vence em desempenho e CPU do coletor.", {})]], line_size=13)
card(s, Inches(4.74), Inches(4.95), Inches(3.85), Inches(1.75), AZUL, "Sysstat",
     [[("Mais leve em memória; simples e portável.", {})]], line_size=13)
card(s, Inches(8.83), Inches(4.95), Inches(3.87), Inches(1.75), LARANJA, "Prometheus",
     [[("Maior custo de memória; ganho só com scraping real.", {})]], line_size=13)

# 17 - CONCLUSOES
s = slide(); header(s, "Fechamento", "Conclusões", 17)
tb, tf = textbox(s, Inches(0.65), Inches(1.95), Inches(12.05), Inches(4.7))
for i, b in enumerate([
    [("A hipótese se confirma: ", {"bold": True, "color": VERDE}), ("o eBPF tem o menor tempo de resposta e a menor CPU de coletor, sem sobrecarregar o WAF.", {})],
    [("Vantagem ", {}), ("consistente e significativa", {"bold": True}), (", porém de magnitude moderada (8–15%) e com maior variabilidade.", {})],
    [("Não há \"ganhador absoluto\": a escolha depende do ", {}), ("contexto operacional", {"bold": True}), (" (memória escassa, ecossistema, latência previsível).", {})],
    [("Contribuição: primeiro ", {}), ("benchmark direto das três", {"bold": True, "color": VERDE}), (" sobre uma mesma VNF, com código aberto e reprodutível.", {})],
]):
    para(tf, b, size=18, bullet=True, space_after=18, first=(i == 0))

# 18 - LIMITACOES E FUTUROS
s = slide(); header(s, "Honestidade científica", "Limitações e trabalhos futuros", 18)
card(s, Inches(0.65), Inches(1.95), Inches(5.85), Inches(4.6), LARANJA, "Limitações",
     [[("Tráfego em loopback (sem overhead de NIC física).", {})],
      [("Contêineres compartilham núcleos → possível contenção.", {})],
      [("WAF simplificado em Python (não é ModSecurity).", {})],
      [("Prometheus sem servidor central fazendo scraping.", {})]], line_size=15)
card(s, Inches(6.85), Inches(1.95), Inches(5.85), Inches(4.6), VERDE, "Trabalhos futuros",
     [[("Estender para uma SFC completa (firewall + IDS + LB).", {})],
      [("Medir em rede física e sob ataque DDoS real.", {})],
      [("Incluir o ciclo de scraping do Prometheus.", {})],
      [("Explorar hooks XDP / TC do eBPF.", {})]], line_size=15)

# 19 - ENCERRAMENTO
s = slide()
bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), SH)
bar.fill.solid(); bar.fill.fore_color.rgb = VERDE; bar.line.fill.background(); bar.shadow.inherit = False
tb, tf = textbox(s, Inches(1.1), Inches(0), Inches(11.2), SH, MSO_ANCHOR.MIDDLE, autoshrink=False)
para(tf, [("Obrigado!", {"size": 46, "bold": True, "color": TXT})], space_after=10, first=True)
para(tf, [("Dúvidas e considerações da banca", {"size": 20, "color": MUT})], space_after=26)
para(tf, [("Rafael Correia Alves   ·   João Pedro dos Santos Henrique Plinta", {"size": 15, "color": TXT})], space_after=6)
para(tf, [("github.com/joaopedroplinta/vnf-monitoring-benchmark", {"size": 13, "color": VERDE, "bold": True})])

prs.save(OUT)
print("OK ->", OUT)
print("Slides:", len(prs.slides._sldIdLst))
