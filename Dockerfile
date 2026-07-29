# Both frontend stages import ../shared/theme.css, so each one recreates the
# repo-relative layout (/repo/shared next to /repo/<app>) rather than flattening.

# python:3.11.15-slim-trixie (multi-platform manifest)
FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93 AS input-verifier

WORKDIR /repo
COPY scripts/verify_build_inputs.py ./scripts/verify_build_inputs.py
COPY deploy/assets.sha256.json ./deploy/assets.sha256.json
COPY frontend/package.json frontend/package-lock.json ./frontend/
COPY web/package.json web/package-lock.json ./web/
RUN python scripts/verify_build_inputs.py --network-assets \
    && touch /verified-build-inputs

# --- Operator live desk (Vite/React SPA, served at /dashboard) ----------------
# node:24-bookworm-slim (multi-platform manifest)
FROM node:24-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d AS frontend-build

WORKDIR /repo
COPY --from=input-verifier /verified-build-inputs /verified-build-inputs
COPY shared ./shared

WORKDIR /repo/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/approval.html frontend/tsconfig.json frontend/tsconfig.node.json frontend/vite.config.ts ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN npm run build

# Export-only proof target used by the descriptor drafter. `scratch` has no
# mutable base image and exposes only the bytes served by the runtime.
FROM scratch AS frontend-proof
COPY --from=frontend-build /repo/frontend/dist /surface

# --- Public marketing site (Next.js static export, served at /) --------------
# Independent of the stage above, so BuildKit runs both concurrently.
# node:24-bookworm-slim (multi-platform manifest)
FROM node:24-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d AS web-build

ARG SAPPHIRE_BUILD_SHA=local-development
ENV SAPPHIRE_BUILD_SHA=${SAPPHIRE_BUILD_SHA}

WORKDIR /repo
COPY --from=input-verifier /verified-build-inputs /verified-build-inputs
COPY shared ./shared

WORKDIR /repo/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/next.config.ts web/tsconfig.json web/postcss.config.mjs ./
COPY web/src ./src
# The published research corpus. lib/research.ts reads it at build time to
# enumerate /research/[slug] via generateStaticParams(); without it the directory
# is absent, the corpus reads as empty, and `output: export` fails the build with
# the misleading "missing generateStaticParams()" (see the note in lib/research.ts).
COPY web/content ./content
RUN npm run build

FROM scratch AS web-proof
COPY --from=web-build /repo/web/out /surface

# --- Runtime ------------------------------------------------------------------
# python:3.11.15-slim-trixie (multi-platform manifest)
FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93

WORKDIR /app

ARG SAPPHIRE_BUILD_SHA=local-development
ARG SAPPHIRE_BUILD_ID=unknown

COPY backend/requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY backend/ ./backend/
COPY --from=frontend-build /repo/frontend/dist ./frontend/dist
COPY --from=web-build /repo/web/out ./web/out

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV SAPPHIRE_BUILD_SHA=${SAPPHIRE_BUILD_SHA}
ENV SAPPHIRE_BUILD_ID=${SAPPHIRE_BUILD_ID}
LABEL org.opencontainers.image.revision=${SAPPHIRE_BUILD_SHA}
LABEL io.sapphire.build-id=${SAPPHIRE_BUILD_ID}

EXPOSE 8080

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
