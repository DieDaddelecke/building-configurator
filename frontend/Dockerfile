# Statisches Frontend mit Caddy; leitet /api an den API-Container weiter (Plan 6.2: eine Domain)
FROM node:24-bookworm-slim AS build
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /src
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm run build

# Caddy selbst bauen: Das offizielle Image hinkt bei Go und Bibliotheken hinterher (Trivy in CI, 14.09.2026).
# Beim nächsten Caddy-Release prüfen, ob die Ersetzungen noch nötig sind.
FROM golang:1.26-alpine AS caddy
ENV CGO_ENABLED=0
RUN go install github.com/caddyserver/xcaddy/cmd/xcaddy@v0.4.7
WORKDIR /build
RUN xcaddy build v2.11.4 \
      --replace golang.org/x/crypto=golang.org/x/crypto@v0.57.0 \
      --replace golang.org/x/net=golang.org/x/net@v0.59.0 \
      --replace golang.org/x/text=golang.org/x/text@v0.42.0 \
      --replace google.golang.org/grpc=google.golang.org/grpc@v1.83.2

FROM caddy:2.11.4-alpine AS runtime
RUN apk upgrade --no-cache
COPY --from=caddy /build/caddy /usr/bin/caddy
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/dist /srv
ENV XDG_DATA_HOME=/tmp XDG_CONFIG_HOME=/tmp
USER 10001
EXPOSE 8080
