# Staff app (queue / display board / admin): Vite build -> nginx (static + API/WebSocket proxy).
FROM node:24-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Same-origin API: nginx proxies to the backend.
ENV VITE_API_URL=""
RUN npx tsc --noEmit && npx vite build --outDir dist --emptyOutDir

FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80
