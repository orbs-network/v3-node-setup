FROM mcr.microsoft.com/devcontainers/typescript-node:18 AS base
WORKDIR /app
COPY package*.json ./

FROM base AS dependencies
RUN npm ci

FROM dependencies AS build
COPY . .
RUN npm run build

FROM node:18-alpine AS release
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY --from=dependencies /app/node_modules ./node_modules
COPY .version ./.version

EXPOSE 80
CMD ["node", "./dist/main.js"]