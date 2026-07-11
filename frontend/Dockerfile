FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine

# nginx-образ сам прогоняет envsubst по /etc/nginx/templates/*.template;
# BACKEND_URL задаётся окружением (в k8s — адрес сервиса бэкенда).
# NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1 велит entrypoint'у экспортировать
# NGINX_LOCAL_RESOLVERS из /etc/resolv.conf (нужен для runtime-резолва).
ENV BACKEND_URL=http://backend:8000 \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
