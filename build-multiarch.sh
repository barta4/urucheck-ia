#!/bin/bash

# Script para construir imágenes multi-arquitectura (amd64 y arm64)
# Requiere docker buildx

# Configuración
REGISTRY="tu-usuario-docker" # Cambia esto por tu usuario de Docker Hub o URL de registry
APP_NAME="urucheck"

echo "🚀 Iniciando construcción multi-arquitectura para $APP_NAME..."

# Crear constructor multi-arch si no existe
docker buildx create --name multiarch-builder --use 2>/dev/null || docker buildx use multiarch-builder

# Construir Backend
echo "📦 Construyendo Backend..."
docker buildx build --platform linux/amd64,linux/arm64 \
  -t $REGISTRY/$APP_NAME-backend:latest \
  -t $REGISTRY/$APP_NAME-backend:$(date +%Y%m%d) \
  ./backend --push

# Construir Frontend Admin
echo "📦 Construyendo Frontend Admin..."
docker buildx build --platform linux/amd64,linux/arm64 \
  -t $REGISTRY/$APP_NAME-frontend:latest \
  -t $REGISTRY/$APP_NAME-frontend:$(date +%Y%m%d) \
  ./frontend-admin --push

echo "✅ Construcción completada y subida a $REGISTRY"
