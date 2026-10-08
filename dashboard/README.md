# VNF Lab

Online: https://vnf-lab.up.railway.app

Dashboard interativo dos resultados do TCC, feito com Streamlit, Plotly e pandas.

Execute a partir da pasta `dashboard/` (o Streamlit lê o tema de `dashboard/.streamlit/config.toml` na pasta de execução):

```bash
cd dashboard
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
python3 build_data.py
.venv/bin/streamlit run app.py
```

Abra `http://localhost:8501`. A configuração visual fica em `dashboard/.streamlit/config.toml` e `dashboard/style.css`.

O botão **Tema**, no canto superior direito, abre o seletor nativo para os modos **Light** (claro), **Dark** (escuro) e **System** (seguir o sistema). A preferência é salva pelo Streamlit no navegador. Os painéis, gráficos, filtros e tabelas acompanham a troca sem reiniciar a sessão. Requer Streamlit 1.65+ e um navegador moderno com suporte a CSS `light-dark()`.

As seis abas oferecem uma visão geral, latência com IC95%, recursos, execuções individuais, dados para download e metodologia. Os filtros laterais são globais. O resumo da visão geral combina as execuções dos volumes selecionados; os intervalos e sua separação são calculados por ferramenta e volume. O CSV exportado contém somente o recorte selecionado, com as colunas originais.

Os dados são experimentais, sem monitoramento em tempo real. A fonte Manrope é carregada pelo Google Fonts, com fallback local para sans-serif.

Validação das agregações e dos filtros:

```bash
cd dashboard && .venv/bin/python -m unittest discover -s tests -v
```

## Hospedagem na Railway

O serviço `vnf-lab` está publicado na Railway (https://vnf-lab.up.railway.app), a partir da branch `main`. Para recriá-lo, crie um serviço a partir do repositório e defina **Root Directory = `dashboard`**. O `railway.json` define o comando de início (`streamlit run app.py` na porta `$PORT`) e o *healthcheck*; as dependências vêm do `requirements.txt`. Gere o domínio público em *Settings → Networking → Generate Domain*. Para atualizar os dados, rode `build_data.py`, faça commit do `data.csv` e envie para a branch do serviço.
