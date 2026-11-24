# Patient kiosk: Vite build -> nginx (static files + API proxy to the backend).
FROM node:24-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# The repo's vite config writes to ../static (served by FastAPI in dev); build into dist here.
# API calls are same-origin (proxied by nginx); the kiosk key is injected by nginx, not baked in.
ENV VITE_API_URL="" VITE_KIOSK_KEY=""
RUN npx tsc && npx vite build --outDir dist --emptyOutDir

FROM nginx:1.29-alpine
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /src/dist /usr/share/nginx/html
# Only substitute our variable; nginx $variables in the template are left alone.
ENV KIOSK_PROXY_KEY="" NGINX_ENVSUBST_FILTER="^KIOSK_PROXY_KEY$"
EXPOSE 80
