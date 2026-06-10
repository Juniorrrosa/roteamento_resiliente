# ---- Stage 1: build do bundle estatico ----
FROM node:20-alpine AS build
WORKDIR /app

# Instala deps primeiro (cache de camada)
COPY package.json ./
RUN npm install

# Copia o codigo e gera o build de producao em /app/dist
COPY . .
RUN npm run build

# ---- Stage 2: serve via nginx ----
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
