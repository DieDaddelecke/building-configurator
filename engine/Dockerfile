# Rechendienst (docs/PLAN_HAUSMODELL.md 3.3). Build-Kontext ist der Wurzelordner: docker build -f engine/Dockerfile .
FROM node:24-bookworm-slim AS build
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /src
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm fetch --frozen-lockfile
COPY . .
RUN pnpm install --offline --frozen-lockfile --filter @emprise/engine... \
    && pnpm --filter @emprise/engine run build

# Laufzeit: nur Node und das Bündel (Kern und clipper2-ts eingebunden), ohne npm, Corepack und Yarn
FROM node:24-bookworm-slim AS runtime
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/corepack \
       /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack \
       /opt/yarn-* /usr/local/bin/yarn /usr/local/bin/yarnpkg
WORKDIR /app
COPY --from=build /src/engine/dist/server.mjs ./server.mjs
USER 10001
ARG RELEASE=dev
ENV NODE_ENV=production EMPRISE_RELEASE=${RELEASE} PORT=8090
EXPOSE 8090
CMD ["node", "server.mjs"]
