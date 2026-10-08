#!/usr/bin/env python3
"""Confere que o cliente multiprocesso (CLIENT_PROCESSES=N) envia exatamente os mesmos payloads que o original.

Gera um arquivo de payloads pequeno, sobe o WAF numa porta local e roda src/client/client.py com
CLIENT_PROCESSES=1 e N. Compara ALLOW/BLOCK/ERRO e o inspect_count do WAF. Uso: python3 scripts/check_client_variants.py [N] [msgs]
A vazão impressa NÃO vale como resultado do TCC (só a máquina de testes, parada, vale).
"""
import json, os, re, signal, subprocess, sys, tempfile, time

N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
MSGS = int(sys.argv[2]) if len(sys.argv) > 2 else 20000   # múltiplo de 100: o contador do WAF fecha exato
PORT = 18082
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
payloads = tempfile.mktemp(suffix=".bin")
subprocess.run([sys.executable, os.path.join(HERE, "gen_payloads.py"), str(MSGS), "--out", payloads],
               check=True, stdout=subprocess.DEVNULL)


def trial(procs):
    metrics = tempfile.mktemp(suffix=".json")
    env = {**os.environ, "WAF_PORT": str(PORT), "WAF_METRICS_PATH": metrics, "PAYLOADS_FILE": payloads,
           "CLIENT_PROCESSES": str(procs), "WORKERS": "50"}
    waf = subprocess.Popen([sys.executable, os.path.join(ROOT, "src/vnf/waf.py")], env=env, stdout=subprocess.DEVNULL)
    try:
        time.sleep(1)
        out = subprocess.run([sys.executable, os.path.join(ROOT, "src/client/client.py")], env=env,
                             capture_output=True, text=True, timeout=300).stdout
        m = re.search(r"~([\d.]+) msg/s\) — ALLOW:(\d+) BLOCK:(\d+) ERRO:(\d+)", out)
        assert m, f"saída inesperada do cliente:\n{out}"
        time.sleep(0.5)
        return float(m[1]), tuple(map(int, m.groups()[1:])), json.load(open(metrics))["inspect_count"]
    finally:
        waf.send_signal(signal.SIGTERM); waf.wait(timeout=10)
        if os.path.exists(metrics): os.remove(metrics)


try:
    r1, c1, i1 = trial(1)
    rn, cn, inn = trial(N)
finally:
    os.remove(payloads)
assert c1 == cn, f"contagens diferentes: 1 proc {c1}, {N} procs {cn}"
assert c1[2] == 0 and sum(c1) == MSGS, f"erros ou perdas: {c1}"
assert i1 == MSGS and inn == MSGS, f"inspect_count do WAF: {i1} / {inn}, esperado {MSGS}"
print(f"OK: mesmo ALLOW/BLOCK ({c1[0]}/{c1[1]}), 0 erros, inspect_count={MSGS} nas duas variantes")
print(f"vazão do cliente: 1 processo {r1:,.0f} msg/s | {N} processos {rn:,.0f} msg/s ({rn / r1:.2f}x) — só indicativo")
