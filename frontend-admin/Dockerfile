# ── Build stage ─────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install --prefer-offline --no-audit --no-fund
COPY . .
# Build without baking any URL — URL is injected at runtime by entrypoint
RUN npm run build

# ── Serve stage ─────────────────────────────────────────────────────────────
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf

# Copy runtime env injection entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

# Entrypoint injects VITE_API_URL into index.html then starts nginx
ENTRYPOINT ["/docker-entrypoint.sh"]
