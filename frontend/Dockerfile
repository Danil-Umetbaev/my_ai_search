# syntax=docker/dockerfile:1.7


# =========================
# BUILD FRONTEND
# =========================

FROM node:22-alpine AS build

WORKDIR /app


COPY package.json package-lock.json ./


RUN --mount=type=cache,target=/root/.npm \
    npm ci


COPY . .


RUN npm run build



# =========================
# NGINX
# =========================

FROM nginx:1.27-alpine


COPY nginx.conf /etc/nginx/conf.d/default.conf


COPY --from=build /app/dist /usr/share/nginx/html


EXPOSE 80


CMD ["nginx", "-g", "daemon off;"]