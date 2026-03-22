#!/bin/bash
# Script de inicialização do TCC
# Limpa build anterior, cria pasta results e sobe os containers

echo "🧹 Limpando build anterior..."

# Para e remove containers, volumes e imagens do projeto
docker-compose down --volumes --remove-orphans

# Remove imagens antigas do projeto
docker images | grep "tcc_gerenciamento_rede" | awk '{print $3}' | xargs -r docker rmi -f

echo "✅ Limpeza concluída"
echo ""

# Cria a pasta results se não existir
mkdir -p results
echo "✅ Pasta results/ criada"
echo ""

echo "🚀 Iniciando TCC Gerenciamento de Rede..."

# Sobe os containers em background
docker-compose up --build -d

echo ""
echo "📊 Containers rodando! Acompanhe os logs com:"
echo "   docker-compose logs -f"
echo ""
echo "⏳ O relatório comparison.csv será gerado em ~/3 minutos em ./results/"
