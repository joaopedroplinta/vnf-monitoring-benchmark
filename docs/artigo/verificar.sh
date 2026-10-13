#!/bin/sh
# Compila o artigo com o tectonic (XeTeX) para conferir erros e número de páginas.
# O ieeeaccess.cls oficial usa a cor Pantone via pdfTeX (\NewSpotColorSpace), que o tectonic não tem;
# aqui a classe é copiada para uma pasta temporária com essa cor trocada por CMYK. O PDF de entrega
# deve ser gerado com pdfLaTeX (Overleaf), com a classe original desta pasta.
set -e
d=$(mktemp -d)
cp -r ../imagens ../referencias.bib "$d"/
mkdir "$d/artigo"
cp *.tex *.png *.cls "$d/artigo/"
sed -i 's|\\RequirePackage{spotcolor}||; s|\\NewSpotColorSpace{PANTONE}||; s|\\AddSpotColor{PANTONE}.*||; s|\\SetPageColorSpace{PANTONE}%||; s|\\definecolor{accessblue}{spotcolor}.*|\\definecolor{accessblue}{cmyk}{.24,1,1,0}|' "$d/artigo/ieeeaccess.cls"
sed -i 's|\.\./referencias|../referencias|' "$d/artigo/artigo.tex"
cd "$d/artigo"
tectonic -X compile artigo.tex
pdfinfo artigo.pdf | grep Pages || true
cp artigo.pdf "${1:-/tmp/artigo.pdf}"
