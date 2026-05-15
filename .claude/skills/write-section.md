---
description: Generates a ready-to-use academic text section in Portuguese for the TCC. Usage: /write-section <section> where section is: metodologia, resultados, discussao, conclusao, or resumo.
---

The user wants to generate academic text for their TCC.

Valid sections:
- `metodologia` — experimental setup, tools, Docker environment, metrics
- `resultados` — data presentation with tables, actual numbers from JSON files
- `discussao` — interpretation of results, anomalies, eBPF vs traditional tradeoffs
- `conclusao` — final verdict, tool recommendations per scenario, future work
- `resumo` — 250-word abstract of the full work

Steps:
1. Extract the section name from the arguments. If missing or invalid, list the valid options and ask.
2. Use the tcc-writer agent to generate the section. Pass the section name clearly.
3. The tcc-writer will read the result files and produce complete academic text in formal Brazilian Portuguese.
4. Display the generated text in a code block for easy copying.
5. Ask the user if they want to save the output to `docs/<section>.md`.

If the user runs `/write-section resultados` but result files are missing, warn them to run `/run-all` first.
