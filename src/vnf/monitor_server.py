#!/usr/bin/env python3
"""
Servidor UDP de Monitoramento — TCC Gerenciamento de Rede
Porta: 9999 UDP
Lê as métricas salvas pelo WAF e responde a qualquer request UDP com o JSON de métricas.
Os coletores (eBPF, sysstat, Prometheus) medem o tempo de cada request → resposta.
"""
import socket
import json
import os
import time

HOST = '0.0.0.0'
PORT = 9999
METRICS_PATH = "/app/results/vnf_metrics.json"

def load_metrics() -> bytes:
    try:
        with open(METRICS_PATH, "r") as f:
            return f.read().encode("utf-8")
    except Exception:
        return json.dumps({"error": "metrics_unavailable"}).encode("utf-8")

def main():
    print("=" * 50)
    print(f"  Monitor UDP — porta {PORT}")
    print(f"  Responde métricas reais do WAF via UDP")
    print("=" * 50)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"✅ Monitor UDP escutando em {HOST}:{PORT}", flush=True)

    while True:
        try:
            data, addr = sock.recvfrom(256)
            payload = load_metrics()
            sock.sendto(payload, addr)
        except Exception as e:
            print(f"[ERRO] {e}")

if __name__ == "__main__":
    main()