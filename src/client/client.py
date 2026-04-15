#!/usr/bin/env python3
"""
Cliente TCP — TCC Gerenciamento de Rede
Bombardeia o WAF (porta 8080) com o payload fixo (payload.bin).
O payload é idêntico em todos os testes — só a ferramenta de monitoramento muda.
"""
import socket
import time
import os

WAF_HOST     = 'localhost'
WAF_PORT     = 8080
PAYLOAD_PATH = os.path.join(os.path.dirname(__file__), "payload.bin")
NUM_MESSAGES = int(os.environ.get("NUM_MESSAGES", 100))
DELAY        = 1  # segundos entre envios

def load_payload() -> bytes:
    if not os.path.exists(PAYLOAD_PATH):
        raise FileNotFoundError(
            f"payload.bin não encontrado em {PAYLOAD_PATH}.\n"
            f"Execute primeiro: python3 gen_payload.py"
        )
    with open(PAYLOAD_PATH, "rb") as f:
        return f.read()

def wait_for_server(host, port, max_attempts=30) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect((host, port))
            print(f"✅ WAF disponível após {attempt} tentativa(s).")
            return True
        except Exception:
            print(f"⏳ Aguardando WAF... tentativa {attempt}/{max_attempts}")
            time.sleep(1)
    return False

def send_payload(payload: bytes) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(10)
        s.connect((WAF_HOST, WAF_PORT))
        s.sendall(payload)
        s.shutdown(socket.SHUT_WR)  # sinaliza EOF para o WAF parar de ler
        response = s.recv(256).decode("utf-8", errors="replace").strip()
    return response

def main():
    print("=" * 50)
    print(f"  Cliente TCP — WAF {WAF_HOST}:{WAF_PORT}")
    print(f"  Mensagens: {NUM_MESSAGES} | Intervalo: {DELAY}s")
    print("=" * 50)

    payload = load_payload()
    print(f"✅ Payload carregado: {len(payload)/1024:.1f} KB")

    if not wait_for_server(WAF_HOST, WAF_PORT):
        print("❌ WAF não respondeu. Encerrando.")
        return

    print(f"\n🚀 Iniciando bombardeio...")
    allowed = blocked = errors = 0

    for i in range(NUM_MESSAGES):
        t0 = time.time()
        try:
            response = send_payload(payload)
            if response.startswith("BLOCKED"):
                blocked += 1
                status = f"BLOCK | {response}"
            else:
                allowed += 1
                status = f"ALLOW | {response}"
            print(f"[{i+1:03d}/{NUM_MESSAGES}] {status}")
        except Exception as e:
            errors += 1
            print(f"[{i+1:03d}/{NUM_MESSAGES}] ERRO: {e}")

        if i < NUM_MESSAGES - 1:
            elapsed = time.time() - t0
            remaining_delay = DELAY - elapsed
            if remaining_delay > 0:
                time.sleep(remaining_delay)

    print(f"\n✅ Concluído — ALLOW:{allowed} BLOCK:{blocked} ERRO:{errors}")

if __name__ == "__main__":
    main()