#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a apresentacao da pre-banca do TCC em PPTX editavel (caixas de texto nativas).
Reaproveita os graficos em docs/imagens/.

Uso:
    python gerar_pptx.py
Saida: docs/apresentacao/apresentacao_tcc.pptx
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---- caminhos ----
BASE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.normpath(os.path.join(BASE, "..", "imagens"))
OUT = os.path.join(BASE, "apresentacao_tcc.pptx")

# ---- paleta ----
AZUL   = RGBColor(0x11, 0x38, 0x5F)
AZUL2  = RGBColor(0x1F, 0x6F, 0xEB)
VERDE  = RGBColor(0x2E, 0x7D, 0x32)
LARANJA= RGBColor(0xE0, 0x8A, 0x00)
CINZA  = RGBColor(0x5B, 0x67, 0x70)
BRANCO = RGBColor(0xFF, 0xFF, 0xFF)
PRETO  = RGBColor(0x22, 0x22, 0x22)
CARD   = RGBColor(0xF4, 0xF7, 0xFB)
VERDE_BG = RGBColor(0xEA, 0xFA, 0xF0)

# ---- dimensoes 16:9 ----
prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = prs.slide_width, prs.slide_height
BLANK = prs.slide_layouts[6]


# ------------------------------------------------------------------ helpers
def slide():
    return prs.slides.add_slide(BLANK)


def bg(s, color):
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = color


def textbox(s, left, top, width, height, anchor=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = Pt(6); tf.margin_right = Pt(6)
    tf.margin_top = Pt(4); tf.margin_bottom = Pt(4)
    return tb, tf


def para(tf, runs, size=18, color=PRETO, bold=False, align=PP_ALIGN.LEFT,
         space_after=6, bullet=False, level=0, first=False):
    """runs: str OU lista de tuplas (texto, {kwargs de run})."""
    p = tf.paragraphs[0] if first and not tf.paragraphs[0].runs else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    p.level = level
    if isinstance(runs, str):
        runs = [(runs, {})]
    for txt, kw in runs:
        r = p.add_run()
        r.text = txt
        r.font.size = Pt(kw.get("size", size))
        r.font.bold = kw.get("bold", bold)
        r.font.italic = kw.get("italic", False)
        r.font.color.rgb = kw.get("color", color)
        r.font.name = "Calibri"
    if bullet:
        _set_bullet(p)
    return p


def _set_bullet(p):
    from pptx.oxml.ns import qn
    pPr = p._pPr
    if pPr is None:
        pPr = p._p.get_or_add_pPr()
    buChar = pPr.makeelement(qn('a:buChar'), {'char': '•'})
    pPr.append(buChar)


def title(s, text, num=None):
    # barra superior
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SW, Inches(1.05))
    bar.fill.solid(); bar.fill.fore_color.rgb = AZUL
    bar.line.fill.background()
    tf = bar.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.5)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = text
    r.font.size = Pt(28); r.font.bold = True; r.font.color.rgb = BRANCO
    r.font.name = "Calibri"
    if num is not None:
        footer(s, num)


def footer(s, num):
    tb, tf = textbox(s, Inches(0.3), Inches(7.05), Inches(8), Inches(0.35))
    para(tf, [("Pré-banca TCC — IFPR Pinhais", {"size": 10, "color": CINZA})], first=True)
    tb2, tf2 = textbox(s, Inches(12.3), Inches(7.05), Inches(0.8), Inches(0.35))
    para(tf2, [(str(num), {"size": 10, "color": CINZA})], align=PP_ALIGN.RIGHT, first=True)


def card(s, left, top, width, height, accent, heading, lines, head_size=16, line_size=12):
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    box.fill.solid(); box.fill.fore_color.rgb = CARD
    box.line.color.rgb = accent; box.line.width = Pt(1)
    # barra de acento a esquerda
    strip = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, Inches(0.08), height)
    strip.fill.solid(); strip.fill.fore_color.rgb = accent
    strip.line.fill.background()
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Pt(12); tf.margin_top = Pt(8); tf.margin_right = Pt(8)
    if heading:
        para(tf, [(heading, {"size": head_size, "bold": True, "color": AZUL})],
             space_after=4, first=True)
    for ln in lines:
        if isinstance(ln, str):
            ln = [(ln, {})]
        para(tf, ln, size=line_size, space_after=3, color=PRETO,
             first=(not heading and ln is lines[0]))
    return box


def pic_fit(s, path, left, top, max_w, max_h):
    """Insere imagem cabendo na caixa, centralizada, preservando proporcao."""
    from PIL import Image
    try:
        with Image.open(path) as im:
            iw, ih = im.size
    except Exception:
        # fallback: deixa o pptx medir
        return s.shapes.add_picture(path, left, top, width=max_w)
    ar = iw / ih
    box_ar = max_w / max_h
    if ar > box_ar:
        w = max_w; h = int(max_w / ar)
    else:
        h = max_h; w = int(max_h * ar)
    l = left + (max_w - w) // 2
    t = top + (max_h - h) // 2
    return s.shapes.add_picture(path, l, t, width=w, height=h)


def caption(s, text, top, left=Inches(0.5), width=Inches(12.3)):
    tb, tf = textbox(s, left, top, width, Inches(0.4))
    para(tf, [(text, {"size": 12, "color": CINZA, "italic": True})],
         align=PP_ALIGN.CENTER, first=True)


# ================================================================== SLIDES

# 1 - CAPA
s = slide(); bg(s, AZUL)
tb, tf = textbox(s, Inches(1), Inches(1.0), Inches(11.3), Inches(5.5), MSO_ANCHOR.MIDDLE)
para(tf, [("INSTITUTO FEDERAL DO PARANÁ — CAMPUS PINHAIS", {"size": 13, "color": RGBColor(0xCF,0xE0,0xF5)})], align=PP_ALIGN.CENTER, space_after=2, first=True)
para(tf, [("Bacharelado em Ciência da Computação", {"size": 13, "color": RGBColor(0xCF,0xE0,0xF5)})], align=PP_ALIGN.CENTER, space_after=18)
para(tf, [("Monitoramento de Funções Virtualizadas de Redes", {"size": 34, "bold": True, "color": BRANCO})], align=PP_ALIGN.CENTER, space_after=6)
para(tf, [("Um estudo comparativo entre ferramentas de extração de comportamento", {"size": 18, "color": RGBColor(0xCF,0xE0,0xF5)})], align=PP_ALIGN.CENTER, space_after=24)
para(tf, [("Rafael Correia Alves  •  João Pedro dos Santos Henrique Plinta", {"size": 15, "color": RGBColor(0xEA,0xF2,0xFB)})], align=PP_ALIGN.CENTER, space_after=4)
para(tf, [("Orientador: Prof. Guilherme Werneck de Oliveira", {"size": 13, "color": RGBColor(0xBC,0xD2,0xEC)})], align=PP_ALIGN.CENTER, space_after=18)
para(tf, [("Pré-banca — Pinhais, 2026", {"size": 12, "color": RGBColor(0x9B,0xB6,0xD6)})], align=PP_ALIGN.CENTER)

# 2 - ROTEIRO
s = slide(); title(s, "Roteiro da apresentação", 2)
tb, tf = textbox(s, Inches(0.6), Inches(1.4), Inches(6.0), Inches(4.2))
for i, t in enumerate([
    "Contexto: NFV e o monitoramento de VNFs",
    "Problema, hipótese e objetivos",
    "As três abordagens comparadas",
    "Lacuna na literatura"], 1):
    para(tf, [(f"{i}.  {t}", {"size": 18})], space_after=10, first=(i == 1))
tb2, tf2 = textbox(s, Inches(6.9), Inches(1.4), Inches(6.0), Inches(4.2))
for i, t in enumerate([
    "Metodologia e arquitetura experimental",
    "Resultados (360 execuções)",
    "Síntese e conclusões",
    "Limitações e trabalhos futuros"], 5):
    para(tf2, [(f"{i}.  {t}", {"size": 18})], space_after=10, first=(i == 5))
card(s, Inches(0.6), Inches(5.7), Inches(12.1), Inches(1.0), AZUL2, "",
     [[("Pergunta central: ", {"size": 15}), ("qual é o custo de monitorar uma VNF?", {"size": 15, "bold": True}),
       (" E qual ferramenta impõe a menor sobrecarga?", {"size": 15})]], line_size=15)

# 3 - CONTEXTO NFV
s = slide(); title(s, "Contexto: Virtualização de Funções de Rede (NFV)", 3)
tb, tf = textbox(s, Inches(0.6), Inches(1.4), Inches(7.0), Inches(5.0))
bullets = [
    [("NFV ", {}), ("desacopla", {"bold": True}), (" funções de rede do hardware dedicado — elas viram software (VNFs) em servidores comuns.", {})],
    [("Exemplos de VNF: firewall, IDS, balanceador, ", {}), ("WAF", {"bold": True}), (".", {})],
    [("Flexibilidade exige ", {}), ("monitoramento constante", {"bold": True}), (": CPU, memória, tráfego, latência.", {})],
    [("O orquestrador (MANO) decide escalar ou recuperar a VNF com base nessas métricas.", {})],
]
for i, b in enumerate(bullets):
    para(tf, b, size=17, bullet=True, space_after=12, first=(i == 0))
card(s, Inches(7.9), Inches(1.6), Inches(4.8), Inches(3.4), AZUL2, "Por que importa",
     [[("Métrica atrasada → o orquestrador reage tarde → violação de SLA.", {})],
      [(" ", {})],
      [("O monitor roda ", {}), ("co-localizado", {"bold": True}), (" à VNF: compete pelos mesmos núcleos de CPU e memória.", {})]],
     line_size=14)

# 4 - PROBLEMA
s = slide(); title(s, "O problema", 4)
tb, tf = textbox(s, Inches(0.6), Inches(1.3), Inches(12.1), Inches(1.1))
para(tf, [("A própria ferramenta de monitoramento ", {"size": 17}), ("consome recursos", {"size": 17, "bold": True}),
          (" que deveriam ir para a VNF. Um coletor pesado degrada justamente o serviço que deveria apenas observar.", {"size": 17})], first=True)
card(s, Inches(0.6), Inches(2.5), Inches(12.1), Inches(1.25), AZUL2, "",
     [[("Pergunta de pesquisa: ", {"size": 15, "bold": True}),
       ("quais as diferenças práticas de desempenho entre eBPF, Sysstat e Prometheus ao monitorar uma VNF, e qual oferece menor sobrecarga sem comprometer a coleta?", {"size": 15})]], line_size=15)
card(s, Inches(0.6), Inches(4.0), Inches(5.9), Inches(2.6), VERDE, "Hipótese",
     [[("O eBPF, por operar no ", {}), ("kernel", {"bold": True}),
       (", deve ter o menor tempo de resposta e o menor impacto, frente ao polling em espaço de usuário (Sysstat e Prometheus via /proc).", {})]], line_size=14)
card(s, Inches(6.8), Inches(4.0), Inches(5.9), Inches(2.6), AZUL2, "Lacuna",
     [[("Faltam estudos ", {}), ("quantitativos controlados", {"bold": True}),
       (" comparando as três abordagens sobre uma mesma VNF, em condições equivalentes.", {})]], line_size=14)

# 5 - OBJETIVOS
s = slide(); title(s, "Objetivos", 5)
tb, tf = textbox(s, Inches(0.6), Inches(1.4), Inches(12.1), Inches(1.2))
para(tf, [("Geral: ", {"size": 18, "bold": True}),
          ("compreender como eBPF, Sysstat e Prometheus influenciam, em tempo de resposta e sobrecarga, o monitoramento de uma VNF sob diferentes cargas.", {"size": 18})], first=True)
tb2, tf2 = textbox(s, Inches(0.6), Inches(2.9), Inches(12.1), Inches(3.5))
para(tf2, [("Específicos:", {"size": 18, "bold": True})], space_after=10, first=True)
for b in [
    "Levantar a literatura de monitoramento em NFV;",
    "Implementar três coletores (eBPF, Sysstat, Prometheus) para um WAF;",
    "Executar experimentos com 4 cargas distintas, medindo tempo de extração, CPU e memória;",
    "Compreender vantagens e limitações de cada abordagem.",
]:
    para(tf2, [(b, {"size": 17})], bullet=True, space_after=10)

# 6 - AS TRES FERRAMENTAS
s = slide(); title(s, "As três abordagens comparadas", 6)
card(s, Inches(0.5), Inches(1.4), Inches(3.95), Inches(4.0), VERDE, "eBPF",
     [[("Kernel-level.", {"bold": True})],
      [("kprobes em tcp_sendmsg e tcp_cleanup_rbuf.", {})],
      [("Conta bytes no kernel via mapas BPF; espaço de usuário só lê o agregado.", {})],
      [("libbpf + CO-RE, sem cópia de pacotes.", {"italic": True, "color": CINZA})]], line_size=13)
card(s, Inches(4.65), Inches(1.4), Inches(3.95), Inches(4.0), AZUL2, "Sysstat",
     [[("User-space.", {"bold": True})],
      [("Polling de /proc/net/dev + psutil a cada requisição.", {})],
      [("Lê e faz parsing de arquivos de texto do /proc.", {})],
      [("Ferramenta consolidada e portável.", {"italic": True, "color": CINZA})]], line_size=13)
card(s, Inches(8.8), Inches(1.4), Inches(3.95), Inches(4.0), LARANJA, "Prometheus",
     [[("User-space.", {"bold": True})],
      [("Mesma lógica do Sysstat + servidor HTTP na porta 8000.", {})],
      [("Expõe /metrics no padrão Prometheus.", {})],
      [("Padrão de observabilidade em microsserviços.", {"italic": True, "color": CINZA})]], line_size=13)
tb, tf = textbox(s, Inches(0.6), Inches(5.7), Inches(12.1), Inches(1.0))
para(tf, [("Núcleo do contraste: ", {"size": 16, "color": CINZA}),
          ("ler contadores no kernel", {"size": 16, "bold": True, "color": AZUL}),
          ("  vs.  ", {"size": 16, "color": CINZA}),
          ("fazer polling de /proc no espaço de usuário.", {"size": 16, "bold": True, "color": AZUL})],
     align=PP_ALIGN.CENTER, first=True)

# 7 - TRABALHOS RELACIONADOS (tabela)
s = slide(); title(s, "Lacuna na literatura", 7)
rows = [
    ("Trabalho", "Tecnologias", "Comparou as 3?", "Carga / VNF"),
    ("Cassagnes et al. (2020)", "eBPF vs. polling", "Não (sem Prometheus)", "Rede geral"),
    ("Sathyaseelan et al. (2024)", "eBPF", "Não", "Kubernetes"),
    ("Shahinfar et al. (2025)", "eBPF", "Não", "Host / rede"),
    ("Oliveira et al. (2026)", "Sysstat", "Não", "DPI simulado"),
    ("Este trabalho", "eBPF + Sysstat + Prometheus", "Sim", "WAF, 100k–2M msgs"),
]
table = s.shapes.add_table(len(rows), 4, Inches(0.6), Inches(1.4), Inches(12.1), Inches(3.6)).table
table.columns[0].width = Inches(3.2)
table.columns[1].width = Inches(3.6)
table.columns[2].width = Inches(2.8)
table.columns[3].width = Inches(2.5)
for c in range(4):
    for r in range(len(rows)):
        cell = table.cell(r, c)
        cell.margin_left = Pt(6); cell.margin_top = Pt(3); cell.margin_bottom = Pt(3)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        run = p.add_run(); run.text = rows[r][c]
        run.font.size = Pt(13); run.font.name = "Calibri"
        if r == 0:
            cell.fill.solid(); cell.fill.fore_color.rgb = AZUL
            run.font.color.rgb = BRANCO; run.font.bold = True
        elif r == len(rows) - 1:
            cell.fill.solid(); cell.fill.fore_color.rgb = VERDE_BG
            run.font.bold = True; run.font.color.rgb = PRETO
        else:
            cell.fill.solid(); cell.fill.fore_color.rgb = BRANCO
            run.font.color.rgb = PRETO
tb, tf = textbox(s, Inches(0.6), Inches(5.4), Inches(12.1), Inches(1.2))
para(tf, [("Nenhum estudo compara as três abordagens sobre uma mesma VNF, com cargas crescentes e controladas. É essa lacuna que preenchemos.", {"size": 16})], first=True)

# 8 - METODOLOGIA
s = slide(); title(s, "Metodologia", 8)
tb, tf = textbox(s, Inches(0.6), Inches(1.5), Inches(7.0), Inches(4.8))
for i, b in enumerate([
    [("Pesquisa ", {}), ("aplicada, quantitativa, comparativa e experimental", {"bold": True}), (".", {})],
    [("VNF representativa: um ", {}), ("WAF", {"bold": True}), (" que inspeciona SQLi, XSS, Path Traversal, RCE e Null Byte.", {})],
    [("WAF concentra carga de CPU → torna visível qualquer sobrecarga do coletor.", {})],
]):
    para(tf, b, size=17, bullet=True, space_after=14, first=(i == 0))
card(s, Inches(7.9), Inches(1.6), Inches(4.8), Inches(3.4), AZUL2, "Ambiente",
     [[("AMD Ryzen 5 5500 (6c/12t), 16 GB RAM", {})],
      [("Ubuntu 26.04 LTS · kernel 7.0.0-15", {})],
      [("3 pilhas Docker Compose isoladas", {})],
      [("libbpf 1.3 · clang 18 · Python 3.12", {})]], line_size=14)

# 9 - ARQUITETURA
s = slide(); title(s, "Arquitetura experimental", 9)
p = os.path.join(IMG, "C4model.drawio.png")
if os.path.exists(p):
    pic_fit(s, p, Inches(1.0), Inches(1.3), Inches(11.3), Inches(4.7))
caption(s, "Cliente → WAF (TCP 8080) → Observador (UDP 9999); probe.py mede o RTT a cada 1 s.", Inches(6.25))

# 10 - PROTOCOLO
s = slide(); title(s, "Protocolo de testes", 10)
tb, tf = textbox(s, Inches(0.6), Inches(1.5), Inches(7.0), Inches(4.8))
for i, b in enumerate([
    [("Variável independente: ", {"bold": True}), ("volume N = 100k, 500k, 1M, 2M mensagens.", {})],
    [("Carga: 60% benigna + 40% maliciosa, semente fixa (42) → idêntica entre ferramentas.", {})],
    [("Cliente: 200 corrotinas assíncronas, conexões TCP persistentes.", {})],
    [("30 repetições por combinação → ", {}), ("360 execuções.", {"bold": True, "color": AZUL2})],
]):
    para(tf, b, size=17, bullet=True, space_after=14, first=(i == 0))
card(s, Inches(7.9), Inches(1.5), Inches(4.8), Inches(4.5), AZUL2, "Métrica primária",
     [[("Tempo de resposta do observador (RTT UDP)", {"bold": True}), (", em nanossegundos pelo probe.py.", {})],
      [(" ", {})],
      [("Secundárias", {"bold": True, "color": AZUL})],
      [("CPU e memória do WAF e do próprio coletor.", {})],
      [(" ", {})],
      [("Agregação: média ± IC95% (t de Student, n=30).", {"italic": True, "color": CINZA})]], line_size=13)

# 11 - TEMPO DE RESPOSTA (principal)
s = slide(); title(s, "Resultado — Tempo de resposta (métrica primária)", 11)
p = os.path.join(IMG, "tempo_resposta_por_n.png")
if os.path.exists(p):
    pic_fit(s, p, Inches(0.4), Inches(1.3), Inches(7.4), Inches(5.4))
tb, tf = textbox(s, Inches(7.9), Inches(1.4), Inches(5.0), Inches(5.2))
para(tf, [("−8% a −15%", {"size": 30, "bold": True, "color": AZUL})], space_after=8, first=True)
para(tf, [("O eBPF teve o menor RTT em todos os volumes.", {"size": 16})], space_after=10)
for b in [
    "Redução de 8,1% a 14,7% vs. Sysstat.",
    "Redução de 10,9% a 14,0% vs. Prometheus.",
    "IC95% nunca se sobrepõem → diferença estatisticamente significativa.",
]:
    para(tf, [(b, {"size": 15})], bullet=True, space_after=8)

# 12 - BOXPLOT
s = slide(); title(s, "Distribuição do tempo de resposta", 12)
p = os.path.join(IMG, "boxplot_tempo_resposta.png")
if os.path.exists(p):
    pic_fit(s, p, Inches(1.2), Inches(1.25), Inches(10.9), Inches(4.6))
tb, tf = textbox(s, Inches(0.6), Inches(5.95), Inches(12.1), Inches(1.0))
para(tf, [("Separação clara: em 500k e 1M, a caixa do eBPF fica inteiramente abaixo das demais. Contrapartida: maior dispersão e outliers (máx. 1,06 ms em 2M).", {"size": 14})], first=True)

# 13 - CPU WAF
s = slide(); title(s, "CPU do WAF — controle", 13)
p = os.path.join(IMG, "cpu_waf.png")
if os.path.exists(p):
    pic_fit(s, p, Inches(0.4), Inches(1.3), Inches(7.4), Inches(5.4))
tb, tf = textbox(s, Inches(7.9), Inches(1.6), Inches(5.0), Inches(4.5))
for i, b in enumerate([
    [("A partir de 500k, o WAF satura em ~107–109% de uma thread, ", {}), ("igual nos três casos", {"bold": True}), (" (IC95% sobrepostos).", {})],
    [("Confirma que nenhum coletor interfere no caminho de inspeção do WAF.", {})],
    [("O coletor afeta sua própria sobrecarga, não a CPU da VNF.", {"italic": True, "color": CINZA})],
]):
    para(tf, b, size=16, space_after=12, first=(i == 0))

# 14 - MEMORIA OBSERVADOR
s = slide(); title(s, "Memória do observador", 14)
p = os.path.join(IMG, "memoria_observador.png")
if os.path.exists(p):
    pic_fit(s, p, Inches(0.4), Inches(1.3), Inches(7.4), Inches(5.4))
tb, tf = textbox(s, Inches(7.9), Inches(1.6), Inches(5.0), Inches(4.7))
para(tf, [("Maior separação entre as abordagens:", {"size": 16})], space_after=10, first=True)
para(tf, [("Sysstat", {"size": 15, "bold": True, "color": AZUL2}), (": ~14 MB (menor)", {"size": 15})], bullet=True, space_after=8)
para(tf, [("eBPF", {"size": 15, "bold": True, "color": VERDE}), (": ~15 MB", {"size": 15})], bullet=True, space_after=8)
para(tf, [("Prometheus", {"size": 15, "bold": True, "color": LARANJA}), (": ~24 MB (+78% vs. Sysstat)", {"size": 15})], bullet=True, space_after=8)
para(tf, [("Custo do servidor HTTP + prometheus_client. Constante com o volume.", {"size": 13, "italic": True, "color": CINZA})], space_after=4)

# 15 - CPU OBSERVADOR
s = slide(); title(s, "CPU do próprio observador", 15)
tb, tf = textbox(s, Inches(0.6), Inches(1.4), Inches(12.1), Inches(0.7))
para(tf, [("Resultado mais limpo em N = 100k:", {"size": 18})], first=True)
rows = [("Coletor", "CPU média do observador"),
        ("eBPF", "0,05% ± 0,01"),
        ("Prometheus", "2,37%"),
        ("Sysstat", "4,66%")]
table = s.shapes.add_table(len(rows), 2, Inches(3.0), Inches(2.2), Inches(7.3), Inches(2.6)).table
table.columns[0].width = Inches(3.0); table.columns[1].width = Inches(4.3)
for r in range(len(rows)):
    for c in range(2):
        cell = table.cell(r, c); cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = Pt(8)
        pp = cell.text_frame.paragraphs[0]
        run = pp.add_run(); run.text = rows[r][c]; run.font.size = Pt(16); run.font.name = "Calibri"
        if r == 0:
            cell.fill.solid(); cell.fill.fore_color.rgb = AZUL; run.font.color.rgb = BRANCO; run.font.bold = True
        elif r == 1:
            cell.fill.solid(); cell.fill.fore_color.rgb = VERDE_BG; run.font.bold = True; run.font.color.rgb = PRETO
        else:
            cell.fill.solid(); cell.fill.fore_color.rgb = BRANCO; run.font.color.rgb = PRETO
tb, tf = textbox(s, Inches(0.6), Inches(5.1), Inches(12.1), Inches(1.6))
para(tf, [("O eBPF consome CPU 1 a 2 ordens de grandeza menor — ler mapas do kernel é muito mais barato que parsear /proc.", {"size": 17})], space_after=8, first=True)
para(tf, [("Em volumes maiores a métrica fica ruidosa (amostragem psutil + contenção entre contêineres) → usada como evidência qualitativa.", {"size": 13, "italic": True, "color": CINZA})])

# 16 - SINTESE
s = slide(); title(s, "Síntese dos resultados", 16)
rows = [
    ("Dimensão", "eBPF", "Sysstat", "Prometheus"),
    ("Tempo de resposta (RTT)", "Menor", "Intermediário", "Maior"),
    ("CPU do WAF", "Equivalente", "Equivalente", "Equivalente"),
    ("Memória do observador", "~15 MB", "~14 MB (menor)", "~24 MB (maior)"),
    ("CPU do observador", "Menor / estável", "Maior / ruidosa", "Maior / ruidosa"),
]
table = s.shapes.add_table(len(rows), 4, Inches(0.6), Inches(1.35), Inches(12.1), Inches(2.9)).table
table.columns[0].width = Inches(3.7)
for c in range(1, 4):
    table.columns[c].width = Inches(2.8)
for r in range(len(rows)):
    for c in range(4):
        cell = table.cell(r, c); cell.vertical_anchor = MSO_ANCHOR.MIDDLE; cell.margin_left = Pt(8)
        pp = cell.text_frame.paragraphs[0]
        run = pp.add_run(); run.text = rows[r][c]; run.font.size = Pt(14); run.font.name = "Calibri"
        if r == 0:
            cell.fill.solid(); cell.fill.fore_color.rgb = AZUL; run.font.color.rgb = BRANCO; run.font.bold = True
        else:
            cell.fill.solid(); cell.fill.fore_color.rgb = BRANCO; run.font.color.rgb = PRETO
            if c == 1 and rows[r][c] in ("Menor", "Menor / estável"):
                run.font.color.rgb = VERDE; run.font.bold = True
            if "menor" in rows[r][c].lower() and c == 2:
                run.font.color.rgb = VERDE; run.font.bold = True
card(s, Inches(0.6), Inches(4.55), Inches(3.9), Inches(2.0), VERDE, "eBPF",
     [[("Vence em desempenho e CPU do coletor.", {})]], line_size=14)
card(s, Inches(4.7), Inches(4.55), Inches(3.9), Inches(2.0), AZUL2, "Sysstat",
     [[("Mais leve em memória; simples e portável.", {})]], line_size=14)
card(s, Inches(8.8), Inches(4.55), Inches(3.9), Inches(2.0), LARANJA, "Prometheus",
     [[("Maior custo de memória; ganho só com scraping real.", {})]], line_size=14)

# 17 - CONCLUSOES
s = slide(); title(s, "Conclusões", 17)
tb, tf = textbox(s, Inches(0.6), Inches(1.5), Inches(12.1), Inches(5.0))
for i, b in enumerate([
    [("A hipótese se confirma: ", {"bold": True, "color": VERDE}), ("o eBPF tem o menor tempo de resposta e a menor CPU de coletor, sem sobrecarregar o WAF.", {})],
    [("A vantagem no RTT é consistente e estatisticamente significativa, porém de magnitude moderada (8–15%) e com maior variabilidade.", {})],
    [("Não há \"ganhador absoluto\": a escolha depende do contexto operacional — memória escassa favorece Sysstat; ecossistema de observabilidade favorece Prometheus.", {})],
    [("Contribuição: primeiro benchmark direto das três sobre uma mesma VNF, com código aberto e reprodutível.", {})],
]):
    para(tf, b, size=18, bullet=True, space_after=16, first=(i == 0))

# 18 - LIMITACOES E FUTUROS
s = slide(); title(s, "Limitações e trabalhos futuros", 18)
card(s, Inches(0.6), Inches(1.5), Inches(5.9), Inches(4.8), AZUL2, "Limitações",
     [[("Tráfego em loopback (sem overhead de NIC física).", {})],
      [("Contêineres compartilham núcleos → possível contenção.", {})],
      [("WAF simplificado em Python (não é ModSecurity).", {})],
      [("Prometheus sem servidor central fazendo scraping.", {})]], line_size=15)
card(s, Inches(6.8), Inches(1.5), Inches(5.9), Inches(4.8), VERDE, "Trabalhos futuros",
     [[("Estender para uma SFC completa (firewall + IDS + LB).", {})],
      [("Medir em rede física e sob ataque DDoS real.", {})],
      [("Incluir o ciclo de scraping Prometheus.", {})],
      [("Explorar hooks XDP/TC do eBPF.", {})]], line_size=15)

# 19 - ENCERRAMENTO
s = slide(); bg(s, AZUL)
tb, tf = textbox(s, Inches(1), Inches(2.2), Inches(11.3), Inches(3.0), MSO_ANCHOR.MIDDLE)
para(tf, [("Obrigado!", {"size": 44, "bold": True, "color": BRANCO})], align=PP_ALIGN.CENTER, space_after=10, first=True)
para(tf, [("Dúvidas e considerações da banca", {"size": 20, "color": RGBColor(0xCF,0xE0,0xF5)})], align=PP_ALIGN.CENTER, space_after=24)
para(tf, [("Rafael Correia Alves  •  João Pedro dos Santos Henrique Plinta", {"size": 15, "color": RGBColor(0xEA,0xF2,0xFB)})], align=PP_ALIGN.CENTER, space_after=4)
para(tf, [("github.com/joaopedroplinta/vnf-monitoring-benchmark", {"size": 13, "color": RGBColor(0xBC,0xD2,0xEC)})], align=PP_ALIGN.CENTER)

prs.save(OUT)
print("OK ->", OUT)
print("Slides:", len(prs.slides._sldIdLst))
