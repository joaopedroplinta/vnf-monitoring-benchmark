#!/bin/sh
# Compila o artigo com pdfLaTeX + BibTeX (o mesmo caminho do Overleaf) e informa erros e número de páginas.
# Precisa de pdflatex no PATH (CI: apt install texlive-latex-extra texlive-fonts-recommended
# texlive-lang-portuguese texlive-bibtex-extra) ou, na falta dele, de uma imagem Docker "tcc-latex" com esses pacotes.
# Roda numa cópia temporária com a mesma estrutura de pastas; o PDF vai para $1 (padrão: /tmp/artigo.pdf).
set -e
d=$(mktemp -d)
cp -r ../imagens ../capítulos ../referencias.bib "$d"/
mkdir "$d/ieee"
cp artigo.tex ieeeaccess.cls IEEEtran.cls IEEEtran.bst bullet.png logo.png notaglinelogo.png t1* "$d/ieee/"
if command -v pdflatex >/dev/null 2>&1; then
  run() { (cd "$d/ieee" && "$@"); }
else
  run() { docker run --rm -v "$d":/w -w /w/ieee tcc-latex "$@"; }
fi
run pdflatex -interaction=nonstopmode -halt-on-error artigo.tex >"$d/log1.txt" || { tail -30 "$d/log1.txt"; exit 1; }
run bibtex artigo >"$d/bib.txt" || { cat "$d/bib.txt"; exit 1; }
run pdflatex -interaction=nonstopmode -halt-on-error artigo.tex >"$d/log2.txt" || { tail -30 "$d/log2.txt"; exit 1; }
run pdflatex -interaction=nonstopmode -halt-on-error artigo.tex >"$d/log3.txt" || { tail -30 "$d/log3.txt"; exit 1; }
grep -E "undefined|Overfull \\\\hbox" "$d/log3.txt" | grep -v "output is active" || true
pdfinfo "$d/ieee/artigo.pdf" | grep Pages
cp "$d/ieee/artigo.pdf" "${1:-/tmp/artigo.pdf}"
