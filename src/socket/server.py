import socket
import time
import threading
import json

class SocketServer:
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
    def start(self):
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        print(f"Servidor ouvindo em {self.host}:{self.port}")
        
        while True:
            client, addr = self.server.accept()
            print(f"Nova conexão de {addr}")
            thread = threading.Thread(target=self.handle_client, args=(client, addr))
            thread.start()
    
    def handle_client(self, client, addr):
        with client:
            while True:
                try:
                    data = client.recv(1024)
                    if not data:
                        break
                    
                    # Processa a mensagem
                    message = data.decode('utf-8')
                    print(f"Recebido de {addr}: {message}")
                    
                    # Responde com echo
                    response = f"Servidor recebeu: {message}"
                    client.send(response.encode('utf-8'))
                    
                    # Se receber "sair", encerra conexão
                    if message.lower() == 'sair':
                        break
                        
                except Exception as e:
                    print(f"Erro: {e}")
                    break
        
        print(f"Conexão encerrada com {addr}")

if __name__ == "__main__":
    server = SocketServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n Servidor encerrado")