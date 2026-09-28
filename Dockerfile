# =============================================================================
# Stage 1: Build Frontend Assets
# =============================================================================
FROM node:22-alpine AS build

WORKDIR /app

# Install dependencies using layer cache
COPY package.json package-lock.json /app/
RUN npm ci

# Copy application source and build bundle
COPY . /app/

ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# =============================================================================
# Stage 2: Production Nginx Runtime
# =============================================================================
FROM nginx:1.27-alpine AS runtime

# Install curl/wget for container health check
RUN apk --no-cache add curl

# Copy custom Nginx reverse proxy configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled SPA static assets from builder stage
COPY --from=build /app/dist /usr/share/nginx/html

# Set correct read permissions
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chmod -R 755 /usr/share/nginx/html

# Expose standard HTTP port
EXPOSE 80

# Health check using dedicated lightweight /healthz location
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:80/healthz || exit 1

STOPSIGNAL SIGQUIT

CMD ["nginx", "-g", "daemon off;"]
