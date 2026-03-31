#!/bin/bash
# Script de inicialização do TCC com Menu de Escolha
# Permite rodar todos os coletores juntos ou um por vez

COL_GREEN="\e[32m"
COL_CYAN="\e[36m"
COL_YELLOW="\e[33m"
COL_RED="\e[31m"
COL_RESET="\e[0m"

clear
echo -e "${COL_CYAN}==============================================================${COL_RESET}"
echo -e "      📊  ${COL_GREEN}TCC Gerenciamento de Rede - Monitoramento TCP${COL_RESET}      "
echo -e "${COL_CYAN}==============================================================${COL_RESET}"
echo -e "Escolha o modo de execução:"
echo -e "  ${COL_YELLOW}[1]${COL_RESET} Rodar TODOS os coletores simultaneamente (Padrão)"
echo -e "  ${COL_YELLOW}[2]${COL_RESET} Rodar eBPF individualmente"
echo -e "  ${COL_YELLOW}[3]${COL_RESET} Rodar sysstat individualmente"
echo -e "  ${COL_YELLOW}[4]${COL_RESET} Rodar Prometheus individualmente"
echo -e "  ${COL_YELLOW}[5]${COL_RESET} Rodar um por vez (Sequencialmente)"
echo -e "  ${COL_YELLOW}[6]${COL_RESET} Apenas gerar o relatório final (Comparator)"
echo -e "  ${COL_YELLOW}[q]${COL_RESET} Sair"
echo -en "\nOpção: "
read opcao

if [[ "$opcao" == "q" ]]; then
    exit 0
fi

# Função para limpar e preparar
preparar() {
    echo -e "\n${COL_CYAN}🧹 Limpando ambiente anterior...${COL_RESET}"
    docker-compose down --volumes --remove-orphans > /dev/null 2>&1
    mkdir -p results
}

# Função para rodar um serviço específico
rodar_servico() {
    local servico=$1
    local duracao=$2
    
    echo -e "\n🚀 Iniciando: ${COL_GREEN}$servico${COL_RESET}..."
    docker-compose up -d server client $servico
    
    echo -e "⏳ Coletando dados por ${COL_YELLOW}$duracao segundos${COL_RESET}..."
    sleep $duracao
    
    echo -e "🛑 Parando containers de $servico..."
    docker-compose stop server client $servico > /dev/null 2>&1
}

gerar_relatorio() {
    echo -e "\n📊 ${COL_GREEN}Gerando relatório final de comparação...${COL_RESET}"
    # O comparator depende dos outros no docker-compose, mas aqui rodamos ele avulso
    docker-compose run --rm comparator sh -c "python3 /app/src/compare.py"
}

case $opcao in
    1)
        preparar
        echo -e "\n🚀 Rodando todos os coletores simultaneamente..."
        docker-compose up -d
        echo -e "⏳ Aguardando 8 minutos de coleta..."
        sleep 485
        gerar_relatorio
        docker-compose down
        ;;
    2)
        preparar
        rodar_servico "ebpf-collector" 485
        gerar_relatorio
        ;;
    3)
        preparar
        rodar_servico "sysstat-collector" 485
        gerar_relatorio
        ;;
    4)
        preparar
        rodar_servico "prometheus-collector" 485
        gerar_relatorio
        ;;
    5)
        preparar
        echo -e "\n🔄 ${COL_YELLOW}Iniciando modo sequencial...${COL_RESET}"
        rodar_servico "ebpf-collector" 485
        rodar_servico "sysstat-collector" 485
        rodar_servico "prometheus-collector" 485
        gerar_relatorio
        ;;
    6)
        gerar_relatorio
        ;;
    *)
        echo -e "${COL_RED}Opção inválida.${COL_RESET}"
        exit 1
        ;;
esac

echo -e "\n✅ ${COL_GREEN}Processo finalizado. Verifique a pasta ./results/${COL_RESET}"
