# VNF Lab

Online: https://vnf-lab.up.railway.app

Dashboard interativo dos resultados do TCC, feito com React, TypeScript, Tailwind CSS e Plotly. É uma página estática: os dados ficam em `dashboard/data.csv` e entram no build.

```bash
cd dashboard
npm install
npm run dev        # http://localhost:5173
npm test           # estatística (média, IC95%, separação dos intervalos) e exportação do CSV
npm run build      # gera dashboard/dist
npm start          # serve dist/ na porta $PORT (padrão 3000)
```

## Dados

`data.csv` tem uma linha por execução. Para regenerá-lo a partir dos JSONs de `results/`:

```bash
python3 dashboard/build_data.py
```

Depois, faça commit do `data.csv`. O build lê o arquivo, então não há servidor de dados.

## O que o painel mostra

Seis abas: visão geral, latência com IC95%, recursos, execuções individuais, dados para download e metodologia. Os filtros laterais (ferramentas, volumes e escala logarítmica) valem para todas as abas. O botão de tema alterna claro, escuro e sistema, e a escolha fica salva no navegador. O CSV exportado contém só o recorte selecionado, com as colunas originais.

Os intervalos de confiança usam t de Student com as 30 repetições de cada combinação. Os dados são experimentais, sem atualização em tempo real.

## Hospedagem na Railway

O serviço `vnf-lab` está publicado na Railway (https://vnf-lab.up.railway.app), a partir da branch `main`. Para recriá-lo, crie um serviço a partir do repositório e defina **Root Directory = `dashboard`**. O `railway.json` define o build (`npm run build`), o comando de início (`npm start`) e o *healthcheck*. Gere o domínio público em *Settings → Networking → Generate Domain*. Para atualizar os dados, rode `build_data.py`, faça commit do `data.csv` e envie para a branch do serviço.
