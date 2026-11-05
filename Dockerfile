# syntax=docker/dockerfile:1

# ---- build ----
FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .

# Public build-time settings (see .env.example). Defaults are production-safe.
ARG VITE_API_URL=/api
ARG VITE_USE_MOCK=false
ARG VITE_POLL_INTERVAL_MS=5000
ARG VITE_API_TIMEOUT_MS=15000
ARG VITE_API_CREDENTIALS=false
ARG VITE_COMPANY_NAME="Your Company Name"
ARG VITE_COMPANY_ADDRESS="Company address, city"
ARG VITE_COMPANY_PHONE="+91 00000 00000"
ARG VITE_COMPANY_EMAIL="info@example.com"
ARG VITE_BASE_PATH=/
ENV VITE_API_URL=$VITE_API_URL \
    VITE_USE_MOCK=$VITE_USE_MOCK \
    VITE_POLL_INTERVAL_MS=$VITE_POLL_INTERVAL_MS \
    VITE_API_TIMEOUT_MS=$VITE_API_TIMEOUT_MS \
    VITE_API_CREDENTIALS=$VITE_API_CREDENTIALS \
    VITE_COMPANY_NAME=$VITE_COMPANY_NAME \
    VITE_COMPANY_ADDRESS=$VITE_COMPANY_ADDRESS \
    VITE_COMPANY_PHONE=$VITE_COMPANY_PHONE \
    VITE_COMPANY_EMAIL=$VITE_COMPANY_EMAIL \
    VITE_BASE_PATH=$VITE_BASE_PATH
RUN pnpm build

# ---- serve ----
FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/healthz || exit 1
