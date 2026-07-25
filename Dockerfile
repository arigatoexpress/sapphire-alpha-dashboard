# --- Operator dashboard (Vite/React SPA, served at /dashboard) ---------------
FROM node:24-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/index.html frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN npm run build

# --- Public marketing site (Next.js static export, served at /) --------------
# Independent of the stage above, so BuildKit runs both concurrently.
FROM node:24-slim AS web-build

WORKDIR /web
COPY web/package.json web/package-lock.json ./
# `npm install` rather than `npm ci` for the same reason as the stage above:
# platform-specific optional dependencies (here, the Next.js SWC binaries)
# differ between the Mac that wrote the lockfile and this linux image.
RUN npm install
COPY web/next.config.ts web/tsconfig.json web/postcss.config.mjs ./
COPY web/src ./src
# `next build` fetches the Google fonts declared via next/font at build time and
# inlines them, so the deployed site makes no third-party font request.
RUN npm run build

# --- Runtime ------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /frontend/dist ./frontend/dist
COPY --from=web-build /web/out ./web/out

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
