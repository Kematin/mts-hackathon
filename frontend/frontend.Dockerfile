FROM node:20-alpine AS builder
ARG FRONTEND_PORT
ENV FRONTEND_PORT=$FRONTEND_PORT
WORKDIR /app
COPY client/package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:stable-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE $FRONTEND_PORT
CMD ["nginx", "-g", "daemon off;"]