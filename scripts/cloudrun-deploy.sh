#!/usr/bin/env bash
# Deploy the MailLens backend to Cloud Run (idempotent; safe to re-run for redeploys).
# Requires: gcloud logged in (gcloud auth login), a project with billing ENABLED BY THE OWNER, Docker.
# Usage: PROJECT=my-project [REGION=europe-west1] scripts/cloudrun-deploy.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/opt/google-cloud-sdk/bin:$HOME/.docker/bin:$HOME/.local/bin:$PATH"
: "${PROJECT:?set PROJECT=<gcp project id>}"
REGION="${REGION:-europe-west1}"
SERVICE=maillens
REPO=maillens
SA="maillens-run@${PROJECT}.iam.gserviceaccount.com"
SECRET=maillens-api-key
TAG="$(git -C "$ROOT" rev-parse --short HEAD)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/backend:${TAG}"

gcloud config set project "$PROJECT" >/dev/null
echo "== enabling APIs (Cloud Run, Artifact Registry, Secret Manager)"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com

echo "== Artifact Registry repository"
gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPO" --repository-format docker --location "$REGION"

echo "== runtime service account (no project roles)"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create maillens-run --display-name "MailLens Cloud Run (no roles)"

echo "== API key in Secret Manager (read from backend/.env via stdin; never printed)"
if ! gcloud secrets describe "$SECRET" >/dev/null 2>&1; then
  grep '^MAILLENS_API_KEY=' "$ROOT/backend/.env" | cut -d= -f2- | tr -d '\n' | \
    gcloud secrets create "$SECRET" --replication-policy automatic --data-file=-
fi
gcloud secrets add-iam-policy-binding "$SECRET" --member "serviceAccount:${SA}" \
  --role roles/secretmanager.secretAccessor >/dev/null

echo "== build (linux/amd64) and push ${IMAGE}"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet >/dev/null
docker buildx build --platform linux/amd64 -t "$IMAGE" --push "$ROOT/backend"

echo "== deploy (scale to zero, max 2 instances, production mode)"
gcloud run deploy "$SERVICE" --image "$IMAGE" --region "$REGION" \
  --service-account "$SA" --set-secrets "MAILLENS_API_KEY=${SECRET}:latest" \
  --cpu 1 --memory 512Mi --concurrency 20 --timeout 20 \
  --min-instances 0 --max-instances 2 --ingress all --allow-unauthenticated --quiet

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')"
echo "$URL" > "$ROOT/.run/url-cloudrun"
echo "== deployed: $URL"
echo "next: MAILLENS_BUILD=prod scripts/push-addon.sh \"$URL\""
