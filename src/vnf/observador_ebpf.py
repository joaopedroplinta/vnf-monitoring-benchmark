#!/usr/bin/env python3
"""
Observador eBPF — TCC Gerenciamento de Rede

Carrega programa BPF pré-compilado (ebpf_kern.o) via ctypes + libbpf.so.
Sem BCC nem LLVM no processo Python (~15 MB RSS).

Requer:
  - /tmp/ebpf_kern.o compilado pelo ebpf_entrypoint.sh
  - libbpf.so.1 instalado (libbpf1 no Ubuntu 24.04)
  - privileged: true, pid: host
"""
import ctypes
import struct
import socket
import json
import os
import sys
import psutil

BPF_OBJ    = os.environ.get("BPF_OBJ_PATH", "/tmp/ebpf_kern.o")
HOST       = "0.0.0.0"
PORT       = 9999
_WAF_METRICS_PATH = os.environ.get("WAF_METRICS_PATH", "/app/results/waf_metrics.json")

# ── Carrega libbpf ────────────────────────────────────────────────────────────

try:
    _lib = ctypes.CDLL("libbpf.so.1", use_errno=True)
except OSError as e:
    print(f"[ERRO] Não foi possível carregar libbpf.so.1: {e}", flush=True)
    sys.exit(1)

# Declarações de tipos e assinaturas da API libbpf
_lib.bpf_object__open.restype  = ctypes.c_void_p
_lib.bpf_object__open.argtypes = [ctypes.c_char_p]

_lib.bpf_object__load.restype  = ctypes.c_int
_lib.bpf_object__load.argtypes = [ctypes.c_void_p]

_lib.bpf_object__find_program_by_name.restype  = ctypes.c_void_p
_lib.bpf_object__find_program_by_name.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

_lib.bpf_program__attach.restype  = ctypes.c_void_p
_lib.bpf_program__attach.argtypes = [ctypes.c_void_p]

_lib.bpf_object__find_map_by_name.restype  = ctypes.c_void_p
_lib.bpf_object__find_map_by_name.argtypes = [ctypes.c_void_p, ctypes.c_char_p]

_lib.bpf_map__fd.restype  = ctypes.c_int
_lib.bpf_map__fd.argtypes = [ctypes.c_void_p]

_lib.bpf_map_lookup_elem.restype  = ctypes.c_int
_lib.bpf_map_lookup_elem.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]

# ── Setup BPF ────────────────────────────────────────────────────────────────

def _setup_bpf():
    obj = _lib.bpf_object__open(BPF_OBJ.encode())
    if not obj:
        print(f"[ERRO] bpf_object__open({BPF_OBJ}) falhou", flush=True)
        sys.exit(1)

    ret = _lib.bpf_object__load(obj)
    if ret < 0:
        print(f"[ERRO] bpf_object__load falhou: {ret}", flush=True)
        sys.exit(1)

    links = []
    for prog_name in (b"kprobe_tcp_sendmsg", b"kprobe_tcp_cleanup_rbuf"):
        prog = _lib.bpf_object__find_program_by_name(obj, prog_name)
        if not prog:
            print(f"[ERRO] programa BPF '{prog_name.decode()}' não encontrado", flush=True)
            sys.exit(1)
        link = _lib.bpf_program__attach(prog)
        if not link:
            print(f"[ERRO] attach de '{prog_name.decode()}' falhou", flush=True)
            sys.exit(1)
        links.append(link)

    bpf_map = _lib.bpf_object__find_map_by_name(obj, b"net_stats")
    if not bpf_map:
        print("[ERRO] mapa 'net_stats' não encontrado", flush=True)
        sys.exit(1)

    map_fd = _lib.bpf_map__fd(bpf_map)
    if map_fd < 0:
        print(f"[ERRO] bpf_map__fd retornou {map_fd}", flush=True)
        sys.exit(1)

    return map_fd, links  # links mantidos em memória para evitar detach

def _map_lookup(map_fd, key_int):
    """Lê um valor u64 de um BPF ARRAY map por chave u32."""
    key_buf = ctypes.create_string_buffer(struct.pack("I", key_int))
    val_buf = ctypes.create_string_buffer(8)
    ret = _lib.bpf_map_lookup_elem(map_fd, key_buf, val_buf)
    if ret < 0:
        return 0
    return struct.unpack("Q", val_buf.raw)[0]

# ── Psutil helpers ────────────────────────────────────────────────────────────

_self_proc = psutil.Process()
_waf_proc  = None

def _find_waf():
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            if "waf.py" in " ".join(proc.info["cmdline"] or []):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def _get_waf_metrics():
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

def _read_waf_metrics():
    try:
        with open(_WAF_METRICS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  Observador eBPF (libbpf) — kprobes sport=8080")
    print("=" * 55)

    map_fd, _links = _setup_bpf()
    print(f"BPF carregado. map_fd={map_fd}. Monitorando sport=8080.", flush=True)

    # Warm-up psutil
    _waf_proc_local = _find_waf()
    if _waf_proc_local:
        _waf_proc_local.cpu_percent(interval=None)
    _self_proc.cpu_percent(interval=None)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"Observador eBPF UDP escutando em {HOST}:{PORT}", flush=True)

    while True:
        try:
            _, addr = sock.recvfrom(256)
            rx  = _map_lookup(map_fd, 0)
            tx  = _map_lookup(map_fd, 1)
            cpu, mem = _get_waf_metrics()
            wm  = _read_waf_metrics()
            resp = json.dumps({
                "bytes_rx":          rx,
                "bytes_tx":          tx,
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
            print(f"[ERRO] {e}", flush=True)

if __name__ == "__main__":
    main()
