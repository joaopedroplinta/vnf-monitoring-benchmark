# 🔍 Monitor de Sockets com eBPF

> Ferramenta de monitoramento de rede em tempo real utilizando eBPF (Extended Berkeley Packet Filter) e Python, desenvolvida como parte do Trabalho de Conclusão de Curso (TCC).

---

## 📋 Sobre o Projeto

Este projeto utiliza **eBPF** para interceptar chamadas de sistema no kernel Linux e monitorar conexões TCP e UDP em tempo real, sem necessidade de modificar o código das aplicações monitoradas.

O monitor captura:
- Conexões **TCP** (`tcp_v4_connect`)
- Mensagens **UDP** (`udp_sendmsg`)
- **PID** e nome do processo responsável
- **IP de origem e destino** com portas
- **Estatísticas agregadas** por processo, porta e IP

---

## 🛠️ Tecnologias

- **Python 3.10**
- **BCC (BPF Compiler Collection)** — biblioteca para programas eBPF em Python
- **eBPF** — tecnologia de sandboxing no kernel Linux
- **Docker + Docker Compose** — ambiente isolado e reproduzível
- **Ubuntu 22.04** — imagem base do container

---

## 📁 Estrutura do Projeto

```
tcc_gerenciamento_rede/
├── Dockerfile            # Imagem Docker com dependências eBPF
├── docker-compose.yml    # Configuração do container
└── src/
    └── monitor.py        # Script principal de monitoramento
```

---

## ⚙️ Pré-requisitos

- **WSL2** com kernel 5.15+ (testado no 6.6.87.2-microsoft-standard-WSL2)
- **Docker** instalado e rodando
- Headers do kernel disponíveis em `/usr/src`

### Verificar suporte a eBPF

```bash
cat /proc/config.gz | gunzip | grep CONFIG_BPF
ls /sys/fs/bpf
```

---

## 🚀 Como Usar

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
cd tcc_gerenciamento_rede
```

### 2. Subir o container

```bash
docker compose up -d
```

### 3. Acessar o container

```bash
docker exec -it ebpf-monitor bash
```

### 4. Rodar o monitor

```bash
# Monitorar tudo (TCP + UDP)
python3 /app/monitor.py

# Só TCP
python3 /app/monitor.py --proto tcp

# Filtrar por processo
python3 /app/monitor.py --proc curl

# Filtrar por porta (ex: HTTPS)
python3 /app/monitor.py --port 443

# Estatísticas a cada 5 segundos
python3 /app/monitor.py --stats 5

# Combinando filtros
python3 /app/monitor.py --proto tcp --port 443 --stats 10
```

---

## 📊 Exemplo de Saída

```
======================================================================
  Monitor de Sockets eBPF - TCC
  Estatísticas a cada 10s
  Ctrl+C para sair
======================================================================
HORA       PROTO PID        PROCESSO           CONEXÃO
----------------------------------------------------------------------
[04:06:23] UDP | PID: 29526  | PROC: curl             | 10.255.255.254:49739 → 10.255.255.254:53
[04:06:23] TCP | PID: 29527  | PROC: curl             | 0.0.0.0:0 → 142.250.79.46:443

======================================================================
  📊 ESTATÍSTICAS — 10s de monitoramento
======================================================================
  Total de eventos : 42
  TCP              : 10
  UDP              : 32

  Top processos:
    curl                 40 eventos
    libuv-worker         2 eventos

  Top portas destino:
    :53       32 eventos
    :443      10 eventos

  Top IPs destino:
    10.255.255.254       32 eventos
    142.250.79.46        10 eventos
======================================================================
```

---

## 🐳 Detalhes do Docker

O container é configurado com:

| Configuração | Valor | Motivo |
|---|---|---|
| `privileged: true` | Habilitado | Necessário para carregar programas eBPF |
| `network_mode: host` | Host | Acesso direto à rede do host |
| `pid: host` | Host | Acesso aos PIDs do host |
| `/sys/fs/bpf` | Montado | Sistema de arquivos BPF |
| `/lib/modules` | Montado | Módulos do kernel |
| `/usr/src` | Montado | Headers do kernel |

---

## 🧠 Como Funciona

1. O script Python compila e carrega um programa C no kernel via BCC
2. O programa eBPF é anexado às funções `tcp_v4_connect` e `udp_sendmsg` via kprobes
3. A cada conexão, o kernel envia um evento pelo `perf_buffer`
4. O Python recebe e exibe os eventos em tempo real

---

## 📚 Referências

- [ebpf.io](https://ebpf.io) — Portal oficial do eBPF
- [BCC Reference Guide](https://github.com/iovisor/bcc/blob/master/docs/reference_guide.md)
- [BCC Python Developer Tutorial](https://github.com/iovisor/bcc/blob/master/docs/tutorial_bcc_python_developer.md)
- [Linux Kernel BPF Docs](https://www.kernel.org/doc/html/latest/bpf/index.html)
- Livro: *Learning eBPF* — Liz Rice (O'Reilly)

---

## 👨‍💻 Autor

Desenvolvido como Trabalho de Conclusão de Curso (TCC).