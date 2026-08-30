#!/bin/sh
# Injected at container startup — writes runtime env vars into index.html
# so the React app can read window.__ENV__.VITE_API_URL without a rebuild.

INDEX="/usr/share/nginx/html/index.html"

# Build the JS snippet with current env values
ENV_SCRIPT="<script>window.__ENV__ = { VITE_API_URL: \"${VITE_API_URL:-/api}\" };</script>"

# Insert it right before </head>  (idempotent: only if not already injected)
if ! grep -q '__ENV__' "$INDEX"; then
  sed -i "s|</head>|${ENV_SCRIPT}</head>|" "$INDEX"
fi

echo "[entrypoint] VITE_API_URL = ${VITE_API_URL:-/api}"

# Start nginx
exec nginx -g 'daemon off;'
