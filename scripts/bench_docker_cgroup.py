#!/usr/bin/env python3
"""Microbenchmark do custo de obter CPU/memória de um contêiner (explica o RTT do coletor Docker).

Mede, em ms por chamada: stats(one_shot) pelo SDK do Docker, ping do daemon (custo da ida e volta
à API) e leitura direta dos arquivos do cgroup. Uso: python3 scripts/bench_docker_cgroup.py [N]
Requer a lib `docker` e cgroup v2 (docker run -d --name bench-cg ... é criado e removido aqui).
"""
import statistics as st, subprocess, sys, time
import docker

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
NAME = "bench-cg"

subprocess.run(["docker", "run", "-d", "--rm", "--name", NAME, "--entrypoint", "sleep",
                "ubuntu:24.04", "900"], check=True, capture_output=True)
try:
    dc = docker.from_env()
    c = dc.containers.get(NAME)
    cg = f"/sys/fs/cgroup/system.slice/docker-{c.id}.scope/"

    def leitura_cgroup():
        for f in ("cpu.stat", "memory.current", "memory.stat"):
            open(cg + f).read()

    for nome, fn in (("stats(one_shot) via SDK", lambda: c.stats(stream=False, one_shot=True)),
                     ("ping do daemon (/_ping)", dc.api.ping),
                     ("leitura direta do cgroup", leitura_cgroup)):
        fn()
        xs = []
        for _ in range(N):
            t = time.perf_counter()
            fn()
            xs.append((time.perf_counter() - t) * 1e3)
        xs.sort()
        print(f"{nome:26} média {st.mean(xs):.3f} ms  mediana {st.median(xs):.3f}  p95 {xs[int(.95 * N)]:.3f}")
finally:
    subprocess.run(["docker", "rm", "-f", NAME], capture_output=True)
