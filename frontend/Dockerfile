# Stage 1: Build React
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

# Vite bakes VITE_* env vars into the built bundle at build time, not runtime -
# this has to be a build arg, not something set later on the running container.
ARG VITE_BACKEND_URL
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
RUN echo "THE BACKEND URL IS: $VITE_BACKEND_URL"
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template

# Cloud Run injects PORT (default 8080); nginx:alpine's entrypoint envsubst's
# templates/*.template into conf.d/ on start, substituting ${PORT} for us.
ENV PORT=8080
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
