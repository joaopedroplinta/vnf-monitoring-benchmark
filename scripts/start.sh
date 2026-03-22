#!/bin/bash
# Script de inicialização do TCC
# Limpa build anterior, cria pasta results e sobe os containers

echo "🧹 Limpando build anterior..."

docker-compose down --volumes --remove-orphans
docker images | grep "tcc_gerenciamento_rede" | awk '{print $3}' | xargs -r docker rmi -f

echo "✅ Limpeza concluída"
echo ""

mkdir -p results
echo "✅ Pasta results/ criada"
echo ""

echo "🚀 Iniciando TCC Gerenciamento de Rede..."
docker-compose up --build -d

echo ""
echo "📊 Containers rodando! Acompanhe os logs com:"
echo "   docker-compose logs -f"
echo ""
echo "⏳ Duração: 15 minutos. O relatório será gerado automaticamente em ./results/"
echo ""
echo "⏰ Aguardando 16 minutos para parar os containers..."
sleep 960

echo ""
echo "🛑 Parando todos os containers..."
docker-compose down
echo "✅ Containers parados. Resultados em ./results/"
