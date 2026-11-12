# Build the static site, then serve the prerendered files with nginx.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# The chat is in the page since 12/11 (Anthropic API engine); build with --build-arg VITE_CHAT=0 to leave it out.
ARG VITE_CHAT=1
# Turnstile's site key is public (the secret lives in the API's env); without one the chat sends no browser proof.
ARG VITE_TURNSTILE_SITEKEY=0x4AAAAAAF-naOwEPdaF6xQz
RUN VITE_CHAT=$VITE_CHAT VITE_TURNSTILE_SITEKEY=$VITE_TURNSTILE_SITEKEY npm run build && node scripts/csp.mjs build/client > build/csp.conf

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build/csp.conf /etc/nginx/csp.conf
COPY --from=build /app/build/client /usr/share/nginx/html
EXPOSE 80
