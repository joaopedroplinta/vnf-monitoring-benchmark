import socket
import time
import random
import sys

class SocketClient:
    def __init__(self, host='localhost', port=9999):
        self.host = host
        self.port = port
        self.socket = None
        
    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        print(f"Conectado ao servidor {self.host}:{self.port}")
        
    def send_message(self, message):
        self.socket.send(message.encode('utf-8'))
        response = self.socket.recv(1024).decode('utf-8')
        return response
    
    def close(self):
        if self.socket:
            self.socket.close()
            
    def simulate_traffic(self, num_messages=10, delay=1):
        try:
            for i in range(num_messages):
                # Gera mensagens aleatórias
                msg_type = random.choice(["ping", "data", "status", "ping", "sair"])
                
                if msg_type == "ping":
                    message = f"PING-{i}"
                elif msg_type == "data":
                    value = random.randint(1, 1000)
                    message = f"DATA:{value}"
                elif msg_type == "status":
                    message = f"STATUS:{random.choice(['OK', 'BUSY', 'ERROR'])}"
                elif msg_type == "sair" and i > 3:  # Só encerra depois de algumas mensagens
                    message = "sair"
                else:
                    message = f"MSG-{i}:{random.random()}"
                
                print(f"Enviando: {message}")
                response = self.send_message(message)
                print(f"Resposta: {response}")
                
                if message.lower() == "sair":
                    break
                    
                time.sleep(delay)
                
        except Exception as e:
            print(f"Erro: {e}")
        finally:
            self.close()
            print("Cliente encerrado")

if __name__ == "__main__":
    import time
    client = SocketClient()

    # Aguarda o servidor estar pronto (até 30 segundos)
    for attempt in range(30):
        try:
            client.connect()
            print(f"✅ Conectado ao servidor após {attempt + 1} tentativa(s).")
            break
        except Exception:
            print(f"⏳ Aguardando servidor... tentativa {attempt + 1}/30")
            time.sleep(1)
    else:
        print("❌ Servidor não respondeu após 30 tentativas. Encerrando.")
        exit(1)

    try:
        # 200 mensagens com 1s de intervalo (~3 min de tráfego)
        client.simulate_traffic(num_messages=200, delay=1)
    except KeyboardInterrupt:
        client.close()
        print("\n⚠️  Cliente interrompido pelo usuário")