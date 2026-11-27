# Node major pinned to the same version already used by .github/workflows/quality-gate.yml's
# frontend-quality job (actions/setup-node node-version: "26"), for consistency between CI
# and the real Compose service this Dockerfile builds (Issue #140, Phase 7).
FROM node:26-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# `shared` resolves via tsconfig.json's "paths" -> "./dist/shared" (classic Angular CLI
# multi-project library resolution), so it must be built before customer-web -- same
# ordering as .github/workflows/quality-gate.yml's frontend-quality job; see
# frontend/README.md's "shared's theme and its .mat-typography class" section.
RUN npx ng build shared
RUN npx ng build customer-web

# Reuses the same unprivileged nginx image/version already vetted for the edge proxy
# (infrastructure/compose/docker-compose.yml's nginx service) for this static-file stage,
# rather than introducing a second base image to track.
FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/customer-web/browser /usr/share/nginx/html

EXPOSE 8080
