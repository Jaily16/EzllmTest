FROM node:24.18.0-alpine@sha256:a0b9bf06e4e6193cf7a0f58816cc935ff8c2a908f81e6f1a95432d679c54fbfd AS build

WORKDIR /app
ARG VUE_APP_API_BASE_URL
ARG VUE_APP_AGENT_API_BASE_URL
ARG VUE_APP_GRAFANA_BASE_URL
ENV VUE_APP_API_BASE_URL=${VUE_APP_API_BASE_URL}
ENV VUE_APP_AGENT_API_BASE_URL=${VUE_APP_AGENT_API_BASE_URL}
ENV VUE_APP_GRAFANA_BASE_URL=${VUE_APP_GRAFANA_BASE_URL}

COPY ez_front_dev/package.json ez_front_dev/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY ez_front_dev/ ./
RUN npm run type-check && npm run build

FROM nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de
COPY ops/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
