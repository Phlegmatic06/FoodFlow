# Multi-stage production Dockerfile for FoodFlow React Frontend
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first for optimal Docker layer caching
COPY package.json package-lock.json* ./
RUN npm ci

# Copy frontend source code
COPY . .

# Build-time environment variables for browser-resolvable backend endpoints
ARG VITE_PROFILE_SERVICE_URL=http://localhost:8001
ARG VITE_RECIPE_SERVICE_URL=http://localhost:8002
ARG VITE_PLANNER_SERVICE_URL=http://localhost:8003

ENV VITE_PROFILE_SERVICE_URL=$VITE_PROFILE_SERVICE_URL \
    VITE_RECIPE_SERVICE_URL=$VITE_RECIPE_SERVICE_URL \
    VITE_PLANNER_SERVICE_URL=$VITE_PLANNER_SERVICE_URL

# Build optimized static distribution
RUN npm run build

# Stage 2: Production Nginx Server
FROM nginx:1.27-alpine AS runner

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration with SPA fallback and gzip
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O - http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
