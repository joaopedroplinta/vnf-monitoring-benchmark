#!/usr/bin/env python3
"""
Cliente TCP — TCC Gerenciamento de Rede
Envia 200 mensagens com 1s de intervalo para o servidor na porta 9999.
Cada mensagem usa uma conexão nova para gerar tráfego visível ao eBPF.
"""
import socket
import time
import random

HOST = 'localhost'
PORT = 9999
NUM_MESSAGES = 200
DELAY = 1  # segundos entre mensagens

def send_message(message: str) -> str:
    """Abre conexão, envia mensagem, recebe resposta, fecha."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        s.sendall(message.encode('utf-8'))
        response = s.recv(1024).decode('utf-8')
    return response

def wait_for_server(max_attempts: int = 30) -> bool:
    for attempt in range(1, max_attempts + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT))
            print(f"✅ Servidor disponível após {attempt} tentativa(s).")
            return True
        except Exception:
            print(f"⏳ Aguardando servidor... tentativa {attempt}/{max_attempts}")
            time.sleep(1)
    return False

def main():
    if not wait_for_server():
        print("❌ Servidor não respondeu. Encerrando.")
        return

    print(f"🚀 Iniciando envio de {NUM_MESSAGES} mensagens (intervalo: {DELAY}s)")

    for i in range(NUM_MESSAGES):
        msg_type = random.choice(["ping", "ping", "data", "status", "msg"])

        if msg_type == "ping":
            message = f"PING-{i}"
        elif msg_type == "data":
            message = f"DATA:{random.randint(1, 1000)}"
        elif msg_type == "status":
            message = f"STATUS:{random.choice(['OK', 'BUSY', 'ERROR'])}"
        else:
            message = f"MSG-{i}:{random.random():.6f}"

        try:
            response = send_message(message)
            print(f"[{i+1:03d}/{NUM_MESSAGES}] Enviado: {message!r:30s} | Resposta: {response!r}")
        except Exception as e:
            print(f"[{i+1:03d}/{NUM_MESSAGES}] Erro ao enviar {message!r}: {e}")

        if i < NUM_MESSAGES - 1:
            time.sleep(DELAY)

    print(f"\n✅ {NUM_MESSAGES} mensagens enviadas. Cliente encerrado.")

if __name__ == "__main__":
    main()