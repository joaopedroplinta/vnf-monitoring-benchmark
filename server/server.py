import socket
import time
import threading
import sys

class SocketServer:
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
    def start(self):
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        print(f"🚀 Servidor iniciado em {self.host}:{self.port}", flush=True)
        print("📡 Aguardando conexões...", flush=True)
        print("-" * 50, flush=True)
        
        while True:
            client, addr = self.server.accept()
            print(f"✅ Nova conexão de {addr[0]}:{addr[1]}", flush=True)
            thread = threading.Thread(target=self.handle_client, args=(client, addr))
            thread.daemon = True
            thread.start()
            print(f"📊 Total de threads ativas: {threading.active_count() - 1}", flush=True)
    
    def handle_client(self, client, addr):
        with client:
            while True:
                try:
                    data = client.recv(1024)
                    if not data:
                        print(f"🔌 Cliente {addr} desconectou", flush=True)
                        break
                    
                    message = data.decode('utf-8')
                    print(f"📨 RECEBIDO de {addr}: '{message}'", flush=True)
                    
                    # Processa a mensagem
                    response = f"Servidor recebeu: {message}"
                    
                    # Simula processamento para algumas mensagens
                    if message.startswith('DATA:'):
                        time.sleep(0.1)  # Simula processamento
                        print(f"⚙️ Processando dados: {message}", flush=True)
                    elif message.startswith('PING'):
                        print(f"🏓 PING recebido, enviando PONG", flush=True)
                    
                    client.send(response.encode('utf-8'))
                    print(f"📤 RESPOSTA para {addr}: '{response}'", flush=True)
                    
                    if message.lower() == 'sair':
                        print(f"👋 Cliente {addr} solicitou desconexão", flush=True)
                        break
                        
                except Exception as e:
                    print(f"❌ Erro com cliente {addr}: {e}", flush=True)
                    break
        
        print(f"📴 Conexão encerrada com {addr}", flush=True)
        print("-" * 50, flush=True)

if __name__ == "__main__":
    print("🖥️  Inicializando servidor socket...", flush=True)
    server = SocketServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n🛑 Servidor encerrado pelo usuário", flush=True)
    except Exception as e:
        print(f"💥 Erro fatal: {e}", flush=True)
    finally:
        print("👋 Servidor finalizado", flush=True)