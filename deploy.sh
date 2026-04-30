#!/bin/bash
# =========================================================
# ElectIQ — Google Cloud Run Deployment Script
# =========================================================
# Usage:
#   Option A (Cloud Build - no Docker required):
#     export GEMINI_API_KEY=your_key_here
#     ./deploy.sh
#
#   Option B (from Google Cloud Shell):
#     1. Upload this repo to Cloud Shell
#     2. export GEMINI_API_KEY=your_key_here
#     3. ./deploy.sh
#
# Prerequisites:
#   - gcloud CLI authenticated (run: gcloud auth login)
#   - Billing enabled on GCP project
# =========================================================

set -e

PROJECT_ID=${1:-"electiq-civic-edu"}
REGION="asia-south1"
SERVICE_NAME="electiq"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo ""
echo "🗳️  ElectIQ — Deploying to Google Cloud Run"
echo "============================================="
echo "  Project:  $PROJECT_ID"
echo "  Region:   $REGION"
echo "  Service:  $SERVICE_NAME"
echo ""

# ── Step 1: Set project ──
echo "📌 Setting GCP project..."
gcloud config set project "$PROJECT_ID"

# ── Step 2: Enable required APIs ──
echo "🔧 Enabling required Google APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com \
  aiplatform.googleapis.com \
  --quiet

# ── Step 3: Build with Cloud Build (no-cache to ensure fresh deploy) ──
echo "🐳 Building Docker image via Cloud Build (no-cache)..."
gcloud builds submit --config cloudbuild.yaml --substitutions="_IMAGE=$IMAGE" --quiet

# ── Step 4: Prepare environment variables ──
ENV_VARS="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION}"
if [ -n "$GEMINI_API_KEY" ]; then
  ENV_VARS="${ENV_VARS},GEMINI_API_KEY=${GEMINI_API_KEY}"
fi
if [ -n "$GOOGLE_SEARCH_API_KEY" ]; then
  ENV_VARS="${ENV_VARS},GOOGLE_SEARCH_API_KEY=${GOOGLE_SEARCH_API_KEY}"
fi
if [ -n "$GOOGLE_SEARCH_CX" ]; then
  ENV_VARS="${ENV_VARS},GOOGLE_SEARCH_CX=${GOOGLE_SEARCH_CX}"
fi

# ── Step 5: Deploy to Cloud Run ──
echo "🚀 Deploying to Cloud Run (region: $REGION)..."
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --timeout 120 \
  --set-env-vars "$ENV_VARS" \
  --quiet

# ── Done ──
echo ""
echo "✅ Deployment complete!"
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format="value(status.url)" 2>/dev/null || echo "")
if [ -n "$SERVICE_URL" ]; then
  echo "🌐 Live at: $SERVICE_URL"
fi
echo ""
echo "📝 Post-deploy checklist:"
echo "   curl ${SERVICE_URL}/api/health"
echo "   - Verify ai_configured: true"
echo "   - Test chat, fact-checker, and quiz features"
