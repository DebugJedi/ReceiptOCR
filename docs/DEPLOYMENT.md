# Deployment Guide

Complete guide to deploying the Receipt OCR system to Google Cloud Run.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Setup](#local-setup)
3. [Google Cloud Setup](#google-cloud-setup)
4. [Google Sheets Setup](#google-sheets-setup)
5. [Anthropic API Setup](#anthropic-api-setup)
6. [Deploy to Cloud Run](#deploy-to-cloud-run)
7. [iPhone Shortcuts Setup](#iphone-shortcuts-setup)
8. [Monitoring & Logging](#monitoring--logging)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Accounts
- ✅ Google Cloud account with billing enabled
- ✅ Anthropic API account
- ✅ Google account for Sheets
- ✅ iPhone with iOS 14+ (for Shortcuts)

### Required Tools
```bash
# Check if installed
python --version  # Should be 3.11+
docker --version
gcloud --version
git --version
```

### Install Missing Tools

**Python 3.11:**
```bash
# macOS
brew install python@3.11

# Ubuntu
sudo apt install python3.11

# Windows
# Download from python.org
```

**Docker:**
```bash
# macOS
brew install --cask docker

# Ubuntu
sudo apt install docker.io

# Windows
# Download Docker Desktop
```

**Google Cloud SDK:**
```bash
# macOS
brew install google-cloud-sdk

# Ubuntu
curl https://sdk.cloud.google.com | bash

# Windows
# Download from cloud.google.com/sdk
```

---

## Local Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/receipt-ocr.git
cd receipt-ocr
```

### 2. Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create Environment File

```bash
cp .env.example .env
```

Edit `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
GOOGLE_CREDS_JSON={"type":"service_account",...}
spreadsheet_id=your-google-sheet-id
system_API=your-optional-auth-key
```

### 5. Test Locally

```bash
python OCR_app.py
```

Visit: http://localhost:8000

Expected output:
```json
{
  "status": "healthy",
  "service": "Receipt OCR API v3.0"
}
```

---

## Google Cloud Setup

### 1. Create Project

```bash
# Set project ID (must be globally unique)
export PROJECT_ID=receipt-ocr-$(date +%s)

# Create project
gcloud projects create $PROJECT_ID --name="Receipt OCR"

# Set as active project
gcloud config set project $PROJECT_ID
```

### 2. Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com
```

### 3. Set Up Billing

```bash
# List billing accounts
gcloud beta billing accounts list

# Link billing account to project
gcloud beta billing projects link $PROJECT_ID \
  --billing-account=BILLING_ACCOUNT_ID
```

### 4. Configure Authentication

```bash
gcloud auth login
gcloud auth configure-docker
```

---

## Google Sheets Setup

### 1. Create Spreadsheet

1. Go to [Google Sheets](https://sheets.google.com)
2. Create a new spreadsheet
3. Name it "Receipt Tracker" or similar
4. Copy the spreadsheet ID from URL:
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
   ```

### 2. Enable Sheets API

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project
3. Navigate to "APIs & Services" > "Library"
4. Search for "Google Sheets API"
5. Click "Enable"

### 3. Create Service Account

```bash
# Create service account
gcloud iam service-accounts create receipt-ocr-sa \
  --display-name="Receipt OCR Service Account"

# Get service account email
export SA_EMAIL=$(gcloud iam service-accounts list \
  --filter="displayName:Receipt OCR Service Account" \
  --format='value(email)')

echo $SA_EMAIL
```

### 4. Generate Credentials

```bash
# Create key file
gcloud iam service-accounts keys create credentials.json \
  --iam-account=$SA_EMAIL

# Convert to single-line JSON for environment variable
cat credentials.json | jq -c . > credentials_oneline.json
```

### 5. Share Sheet with Service Account

1. Open your Google Sheet
2. Click "Share" button
3. Add the service account email (`$SA_EMAIL`)
4. Grant "Editor" permission
5. Uncheck "Notify people"
6. Click "Done"

### 6. Update .env File

```bash
# Add to .env
echo "GOOGLE_CREDS_JSON=$(cat credentials_oneline.json)" >> .env
echo "spreadsheet_id=YOUR_SPREADSHEET_ID" >> .env
```

---

## Anthropic API Setup

### 1. Create Account

1. Visit [Anthropic Console](https://console.anthropic.com)
2. Sign up or log in
3. Navigate to "API Keys"

### 2. Generate API Key

1. Click "Create Key"
2. Name it "Receipt OCR"
3. Copy the key (starts with `sk-ant-`)
4. **Save it securely** (you won't see it again!)

### 3. Add to Environment

```bash
echo "ANTHROPIC_API_KEY=sk-ant-xxxxx" >> .env
```

### 4. Verify Credits

Check your account has credits:
- Free tier: $5 credit
- Paid tier: Add payment method

---

## Deploy to Cloud Run

### Method 1: Using gcloud (Recommended)

```bash
# Build and deploy in one command
gcloud run deploy receipt-ocr \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 60s \
  --max-instances 10 \
  --set-env-vars ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY .env | cut -d '=' -f2-) \
  --set-env-vars GOOGLE_CREDS_JSON=$(grep GOOGLE_CREDS_JSON .env | cut -d '=' -f2-) \
  --set-env-vars spreadsheet_id=$(grep spreadsheet_id .env | cut -d '=' -f2-)
```

Wait for deployment (2-5 minutes).

### Method 2: Using Docker

```bash
# Build image
docker build -t gcr.io/$PROJECT_ID/receipt-ocr .

# Push to Container Registry
docker push gcr.io/$PROJECT_ID/receipt-ocr

# Deploy
gcloud run deploy receipt-ocr \
  --image gcr.io/$PROJECT_ID/receipt-ocr \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --set-env-vars ANTHROPIC_API_KEY=xxx,GOOGLE_CREDS_JSON=xxx,spreadsheet_id=xxx
```

### 3. Get Service URL

```bash
export SERVICE_URL=$(gcloud run services describe receipt-ocr \
  --region us-central1 \
  --format='value(status.url)')

echo "Your API is live at: $SERVICE_URL"
```

### 4. Test Deployment

```bash
# Health check
curl $SERVICE_URL

# Test with receipt
curl -X POST $SERVICE_URL/receipt \
  -F "file=@tests/test_receipts/sample.jpg"
```

---

## iPhone Shortcuts Setup

### 1. Open Shortcuts App

On your iPhone, open the **Shortcuts** app.

### 2. Create New Shortcut

1. Tap **+** to create new shortcut
2. Tap **Add Action**
3. Search for "Receive"

### 3. Add Actions

**Action 1: Receive Input**
```
Receive [Images] input from Share Sheet
```

**Action 2: Set Variable**
```
Set variable [Image] to [Shortcut Input]
```

**Action 3: Get Contents of URL**
```
URL: YOUR_SERVICE_URL/receipt
Method: POST
Headers:
  Content-Type: multipart/form-data
Body: Form
  file: [Image]
```

**Action 4: Get Dictionary**
```
Get Dictionary from [Contents of URL]
```

**Action 5: Get Value**
```
Get [store_name] from [Dictionary]
Get [total] from [Dictionary]
Get [item_count] from [Dictionary]
```

**Action 6: Show Notification**
```
Title: Receipt Processed!
Body: [store_name] - $[total] - [item_count] items
```

### 4. Configure Settings

1. Tap shortcut name (top)
2. Rename to "Process Receipt"
3. Tap icon to change appearance
4. Enable "Show in Share Sheet"
5. Select "Images" and "Photos" as accepted types

### 5. Test Shortcut

1. Open Photos app
2. Select a receipt photo
3. Tap Share button
4. Select "Process Receipt"
5. Wait for notification

---

## Monitoring & Logging

### View Logs

```bash
# Real-time logs
gcloud run services logs tail receipt-ocr --region us-central1

# Last 100 entries
gcloud run services logs read receipt-ocr \
  --region us-central1 \
  --limit 100
```

### Cloud Console

1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Click on "receipt-ocr" service
3. Click "LOGS" tab

### Set Up Alerts

```bash
# Create alert policy for errors
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="Receipt OCR Errors" \
  --condition-display-name="High error rate" \
  --condition-threshold-value=10 \
  --condition-threshold-duration=300s
```

### Metrics Dashboard

View metrics:
- Request count
- Latency (p50, p95, p99)
- Error rate
- Memory usage
- CPU usage

Access: Cloud Console > Cloud Run > receipt-ocr > METRICS

---

## Troubleshooting

### Issue: Deployment Fails

**Error:** "Permission denied"

**Solution:**
```bash
# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/run.admin"
```

---

### Issue: 503 Service Unavailable

**Cause:** Cold start or insufficient resources

**Solution:**
```bash
# Increase memory
gcloud run services update receipt-ocr \
  --region us-central1 \
  --memory 1Gi

# Set minimum instances (avoid cold starts)
gcloud run services update receipt-ocr \
  --region us-central1 \
  --min-instances 1
```

**Warning:** min-instances=1 incurs charges even when idle

---

### Issue: Timeout Errors

**Cause:** Image too large or slow API response

**Solution:**
```bash
# Increase timeout
gcloud run services update receipt-ocr \
  --region us-central1 \
  --timeout 120s
```

---

### Issue: Google Sheets Not Updating

**Check:**
1. Service account has Editor access to sheet
2. Spreadsheet ID is correct
3. GOOGLE_CREDS_JSON is valid JSON

**Test:**
```bash
python gsheet.py
# Should see: "✅ Test complete. Check your Google Sheet!"
```

---

### Issue: High Costs

**Monitor usage:**
```bash
# View current billing
gcloud billing projects describe $PROJECT_ID

# Set budget alerts
gcloud alpha billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="Receipt OCR Budget" \
  --budget-amount=10USD \
  --threshold-rule=percent=50,percent=90
```

**Optimize costs:**
- Use `--max-instances` to cap scaling
- Implement caching for duplicate receipts
- Compress images before upload

---

## Update Deployment

### Update Code

```bash
# Pull latest changes
git pull

# Redeploy
gcloud run deploy receipt-ocr \
  --source . \
  --region us-central1
```

### Update Environment Variables

```bash
gcloud run services update receipt-ocr \
  --region us-central1 \
  --update-env-vars ANTHROPIC_API_KEY=new-key
```

### Rollback

```bash
# List revisions
gcloud run revisions list --service receipt-ocr --region us-central1

# Rollback to previous revision
gcloud run services update-traffic receipt-ocr \
  --region us-central1 \
  --to-revisions REVISION_NAME=100
```

---

## Production Checklist

Before going to production:

- [ ] Environment variables are secure (not in code)
- [ ] Authentication is enabled (system_API key)
- [ ] Budget alerts are configured
- [ ] Logging is enabled
- [ ] Error monitoring is set up
- [ ] Backup strategy for Google Sheets
- [ ] HTTPS is enforced (default)
- [ ] Rate limiting is configured
- [ ] Documentation is complete
- [ ] Test suite passes

---

## Security Best Practices

### 1. Secret Management

Use Google Cloud Secret Manager:

```bash
# Store secret
echo -n "sk-ant-xxxxx" | gcloud secrets create anthropic-api-key --data-file=-

# Grant access
gcloud secrets add-iam-policy-binding anthropic-api-key \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"

# Update Cloud Run to use secret
gcloud run services update receipt-ocr \
  --region us-central1 \
  --update-secrets=ANTHROPIC_API_KEY=anthropic-api-key:latest
```

### 2. Enable Authentication

In `.env`:
```env
system_API=your-secure-random-key-here
```

Generate secure key:
```bash
openssl rand -base64 32
```

### 3. Restrict Access

```bash
# Remove unauthenticated access
gcloud run services update receipt-ocr \
  --region us-central1 \
  --no-allow-unauthenticated

# Allow specific service account only
gcloud run services add-iam-policy-binding receipt-ocr \
  --region us-central1 \
  --member="serviceAccount:your-app@project.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

### 4. Enable Audit Logs

```bash
gcloud projects update $PROJECT_ID \
  --enable-cloud-logging
```

---

## Cost Estimation

### Google Cloud Run
- **Free Tier:**
  - 2 million requests/month
  - 360,000 GB-seconds
  - 180,000 vCPU-seconds

- **Pricing (beyond free):**
  - $0.40 per million requests
  - $0.00002400 per GB-second
  - $0.00001000 per vCPU-second

**Example:** 1,000 receipts/month
- Requests: Free (under 2M)
- Compute: ~$0.10
- **Total: $0.10/month**

### Anthropic API
- **Claude Sonnet 4:**
  - Input: $3 per million tokens
  - Output: $15 per million tokens

**Example:** 1,000 receipts/month
- Avg input: 2,000 tokens/receipt
- Avg output: 800 tokens/receipt
- Input cost: (1000 × 2000 / 1M) × $3 = $6.00
- Output cost: (1000 × 800 / 1M) × $15 = $12.00
- **Total: $18.00/month**

### Google Sheets API
- **Free** up to quotas

### Total Monthly Cost
- 1,000 receipts: ~$18.10
- 100 receipts: ~$1.80
- 10 receipts: ~$0.18

---

## Support

**Issues:** [GitHub Issues](https://github.com/yourusername/receipt-ocr/issues)  
**Email:** your-email@example.com

---

**Last Updated:** December 8, 2025