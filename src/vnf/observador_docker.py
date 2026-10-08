#!/usr/bin/env python3
"""
Observador docker — TCC Gerenciamento de Rede
Coleta CPU/mem do container do WAF via API do Docker (lib docker → cgroups).
Bytes RX/TX via /proc/net/dev (o WAF usa network_mode host, então as stats de
rede do Docker não refletem o WAF). Serve métricas via UDP :9999.
Requer: /var/run/docker.sock montado.
"""
import socket, json, os, time
import docker
import psutil

HOST      = '0.0.0.0'
PORT      = 9999
INTERFACE = "lo"
WAF_CONTAINER = os.environ.get("WAF_CONTAINER", "waf-server")
_WAF_METRICS_PATH = os.environ.get("WAF_METRICS_PATH", "/app/results/waf_metrics.json")


def _read_waf_metrics() -> dict:
    try:
        with open(_WAF_METRICS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}

_self_proc = psutil.Process()
_client = docker.from_env()
_waf = None    # objeto Container, resolvido no primeiro uso (o WAF sobe antes, mas pode atrasar)
_prev = None   # (instante, cpu_total_ns) da amostra anterior

def get_proc_bytes():
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if INTERFACE in line:
                    parts = line.split()
                    if len(parts) > 9:
                        return int(parts[1]), int(parts[9])
    except Exception as e:
        print(f"[ERRO] get_proc_bytes: {e}", flush=True)
    return 0, 0

def get_waf_metrics():
    """CPU (% de 1 núcleo, como o psutil) e memória (MB) do cgroup do container do WAF."""
    global _waf, _prev
    try:
        if _waf is None:
            _waf = _client.containers.get(WAF_CONTAINER)
        t0 = time.monotonic()
        # one_shot: não espera os 2 ciclos do daemon (~1 s); CPU sai do delta entre chamadas
        s = _waf.stats(stream=False, one_shot=True)
        t = (t0 + time.monotonic()) / 2
        usage = s["cpu_stats"]["cpu_usage"]["total_usage"]  # ns
        cpu = 0.0
        if _prev and t > _prev[0]:
            cpu = (usage - _prev[1]) / ((t - _prev[0]) * 1e9) * 100
        _prev = (t, usage)
        m = s["memory_stats"]
        # mesma conta do `docker stats`: uso do cgroup sem o cache inativo de arquivos
        mem = (m["usage"] - m.get("stats", {}).get("inactive_file", 0)) / 1024 / 1024
        return round(cpu, 2), round(mem, 2)
    except (docker.errors.DockerException, KeyError):
        _waf, _prev = None, None
    return 0.0, 0.0

def main():
    print("=" * 55)
    print("  Observador docker — API do Docker (cgroups) do WAF")
    print("=" * 55)

    start_rx, start_tx = get_proc_bytes()

    get_waf_metrics()  # warm-up: a primeira chamada só grava a amostra base do delta de CPU
    _self_proc.cpu_percent(interval=None)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"Observador docker UDP escutando em {HOST}:{PORT}", flush=True)

    while True:
        try:
            _, addr = sock.recvfrom(256)
            rx, tx = get_proc_bytes()
            cpu, mem = get_waf_metrics()
            wm = _read_waf_metrics()
            resp = json.dumps({
                "bytes_rx":          rx - start_rx,
                "bytes_tx":          tx - start_tx,
                "cpu_pct":           cpu,
                "mem_mb":            mem,
                "collector_cpu_pct": round(_self_proc.cpu_percent(interval=None), 2),
                "collector_mem_mb":  round(_self_proc.memory_info().rss / 1024 / 1024, 2),
                "inspect_count":     wm.get("inspect_count", 0),
                "inspect_avg_ms":    wm.get("inspect_avg_ms", 0.0),
                "inspect_min_ms":    wm.get("inspect_min_ms", 0.0),
                "inspect_max_ms":    wm.get("inspect_max_ms", 0.0),
            }).encode("utf-8")
            sock.sendto(resp, addr)
        except Exception as e:
            print(f"[ERRO] {e}")

if __name__ == "__main__":
    main()
