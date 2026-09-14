# Statisches Frontend mit Caddy; leitet /api an den API-Container weiter (Plan 6.2: eine Domain)
FROM node:24-bookworm-slim AS build
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /src
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm run build

FROM caddy:2-alpine AS runtime
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/dist /srv
ENV XDG_DATA_HOME=/tmp XDG_CONFIG_HOME=/tmp
USER 10001
EXPOSE 8080
