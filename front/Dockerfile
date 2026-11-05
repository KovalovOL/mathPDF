FROM node:24-alpine AS assets
WORKDIR /front
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY app ./app
COPY scripts ./scripts
COPY asset-map.json ./
RUN npm run build

FROM nginx:1.28-alpine
COPY infrastructure/nginx.conf /etc/nginx/nginx.conf
COPY infrastructure/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=assets /front/dist /usr/share/nginx/html
EXPOSE 8080 8081
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD wget -q -O /dev/null http://127.0.0.1:8080/health || exit 1
