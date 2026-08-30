#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# build-images.sh — Construye y sube las imágenes de UruCheck IA a Docker Hub
# Usuario: alfredobartaburu
# Uso:
#   ./build-images.sh            → AMD64 local (para desarrollo/pruebas locales)
#   ./build-images.sh v1.0       → Build y push linux/amd64 con tag específico
#   ./build-images.sh v1.1       → Nueva versión
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY="alfredobartaburu"
APP_BACKEND="urucheck-backend"
APP_FRONTEND="urucheck-frontend"
VERSION=${1:-""}  # Tag de versión pasado como argumento (ej: v1.0)

PLATFORM="linux/amd64"

if [ -z "$VERSION" ]; then
    # Sin argumento → build local AMD64
    echo "⚠️  Sin versión indicada. Build LOCAL para linux/amd64 únicamente."
    ACTION="--load"
    TAG_BACKEND="${APP_BACKEND}:local"
    TAG_FRONTEND="${APP_FRONTEND}:local"
else
    # Con versión → build estándar amd64 y push a Docker Hub (RÁPIDO)
    echo "🚀 Build para linux/amd64 y push a Docker Hub con tag: ${VERSION}"
    ACTION="--push"
    TAG_BACKEND="${REGISTRY}/${APP_BACKEND}:${VERSION}"
    TAG_FRONTEND="${REGISTRY}/${APP_FRONTEND}:${VERSION}"
fi

# Crear/usar constructor multi-arch (solo necesario la primera vez)
docker buildx use multiarch-builder 2>/dev/null || \
    docker buildx create --name multiarch-builder --use

echo ""
echo "📦 Construyendo Backend → ${TAG_BACKEND}"
docker buildx build --platform ${PLATFORM} \
    -t ${TAG_BACKEND} \
    ./backend ${ACTION}

echo ""
echo "📦 Construyendo Frontend → ${TAG_FRONTEND}"
docker buildx build --platform ${PLATFORM} \
    -t ${TAG_FRONTEND} \
    ./frontend-admin ${ACTION}

echo ""
echo "✅ Proceso completado."
if [ -n "$VERSION" ]; then
    echo ""
    echo "Imágenes publicadas:"
    echo "  docker.io/${TAG_BACKEND}"
    echo "  docker.io/${TAG_FRONTEND}"
    echo ""
    echo "Para desplegar, actualizar docker-compose.yml y ejecutar:"
    echo "  docker compose pull && docker compose up -d"
fi
