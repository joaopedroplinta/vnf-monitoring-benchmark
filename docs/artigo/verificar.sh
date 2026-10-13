#!/bin/sh
# Compila o artigo com o tectonic para conferir erros e número de páginas (o PDF de entrega sai do Overleaf, com pdfLaTeX).
# Roda numa cópia temporária com a mesma estrutura de pastas, para não deixar arquivos de compilação no repositório.
set -e
d=$(mktemp -d)
cp -r ../imagens ../referencias.bib "$d"/
mkdir "$d/artigo"
cp *.tex *.png *.cls "$d/artigo/"
cd "$d/artigo"
tectonic -X compile artigo.tex
pdfinfo artigo.pdf | grep Pages || true
cp artigo.pdf "${1:-/tmp/artigo.pdf}"
