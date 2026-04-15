#!/usr/bin/env python3
"""
Monitor sysstat — TCC Gerenciamento de Rede
Coleta bytes RX/TX via /proc/net/dev (loopback) + CPU/mem do processo WAF via psutil.
Serve métricas via UDP :9999.
Requer: pid=host.
"""
import socket, json
import psutil

HOST      = '0.0.0.0'
PORT      = 9999
INTERFACE = "lo"

_waf_proc = None

def get_proc_bytes():
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if INTERFACE in line:
                    parts = line.split()
                    return int(parts[1]), int(parts[9])
    except Exception:
        pass
    return 0, 0

def _find_waf():
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if 'waf.py' in ' '.join(proc.info['cmdline'] or []):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def get_waf_metrics():
    global _waf_proc
    try:
        if _waf_proc is None or not _waf_proc.is_running():
            _waf_proc = _find_waf()
        if _waf_proc:
            return (
                round(_waf_proc.cpu_percent(interval=None), 2),
                round(_waf_proc.memory_info().rss / 1024 / 1024, 2),
            )
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        _waf_proc = None
    return 0.0, 0.0

def main():
    print("=" * 55)
    print("  Monitor sysstat — /proc/net/dev + psutil WAF")
    print("=" * 55)

    start_rx, start_tx = get_proc_bytes()

    # Warm-up: primeira chamada cpu_percent sempre retorna 0
    proc = _find_waf()
    if proc:
        proc.cpu_percent(interval=None)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"Monitor sysstat UDP escutando em {HOST}:{PORT}", flush=True)

    while True:
        try:
            _, addr = sock.recvfrom(256)
            rx, tx = get_proc_bytes()
            cpu, mem = get_waf_metrics()
            resp = json.dumps({
                "bytes_rx": rx - start_rx,
                "bytes_tx": tx - start_tx,
                "cpu_pct":  cpu,
                "mem_mb":   mem,
            }).encode("utf-8")
            sock.sendto(resp, addr)
        except Exception as e:
            print(f"[ERRO] {e}")

if __name__ == "__main__":
    main()
