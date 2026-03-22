#!/bin/bash
# Script de inicialização do TCC
# Cria a pasta results e sobe os containers

echo "🚀 Iniciando TCC Gerenciamento de Rede..."

# Cria a pasta results se não existir
mkdir -p results
echo "✅ Pasta results/ criada"

# Sobe os containers em background
docker-compose up --build -d

echo ""
echo "📊 Containers rodando! Acompanhe os logs com:"
echo "   docker-compose logs -f"
echo ""
echo "⏳ O relatório comparison.csv será gerado em ~/3 minutos em ./results/"
