# API Documentation

## Base URL

```
Production: https://your-project.run.app
Local: http://localhost:8000
```

---

## Authentication

Optional bearer token authentication.

```http
Authorization: Bearer YOUR_API_KEY
```

Set `system_API` in environment variables to enable authentication.

---

## Endpoints

### Health Check

Check if the API is running.

```http
GET /
```

**Response:**
```json
{
  "status": "healthy",
  "service": "Receipt OCR API v3.0",
  "method": "Claude Vision API",
  "endpoints": {
    "POST /receipt": "Process receipt image",
    "GET /": "Health check"
  }
}
```

---

### Process Receipt

Extract structured data from a receipt image.

```http
POST /receipt
```

**Request:**

Headers:
```
Content-Type: multipart/form-data
Authorization: Bearer YOUR_API_KEY (optional)
```

Body:
```
file: <image file>
```

**Supported Image Formats:**
- JPEG (.jpg, .jpeg)
- PNG (.png)
- HEIC (.heic) - iPhone native format

**Size Limits:**
- Maximum: 10MB
- Automatically compressed to <4MB for processing

**Example with cURL:**
```bash
curl -X POST https://your-url.run.app/receipt \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@receipt.jpg"
```

**Example with Python:**
```python
import requests

url = "https://your-url.run.app/receipt"
headers = {"Authorization": "Bearer YOUR_API_KEY"}
files = {"file": ("receipt.jpg", open("receipt.jpg", "rb"), "image/jpeg")}

response = requests.post(url, headers=headers, files=files)
data = response.json()
```

**Example with JavaScript (fetch):**
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('https://your-url.run.app/receipt', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY'
  },
  body: formData
});

const data = await response.json();
```

---

**Response (Success - 200):**

```json
{
  "status": "success",
  "message": "Receipt processed successfully",
  "data": {
    "receipt_id": "3743",
    "store_name": "CVS PHARMACY",
    "address": "11831 Hawthorne Blvd, Hawthorne, CA 90250",
    "phone": "(310) 679-3668",
    "date": "2023-01-10",
    "subtotal": 59.40,
    "tax": 6.48,
    "total": 64.88,
    "payment_method": "VISA",
    "card_last_4": "9284",
    "item_count": 11
  },
  "sheet_update": {
    "rows_added": 12,
    "cells_updated": 144
  }
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "success" or "error" |
| `message` | string | Human-readable message |
| `data.receipt_id` | string | Transaction ID from receipt |
| `data.store_name` | string | Store/merchant name |
| `data.address` | string | Full store address |
| `data.phone` | string | Store phone number |
| `data.date` | string | Receipt date (YYYY-MM-DD) |
| `data.subtotal` | float | Pre-tax amount |
| `data.tax` | float | Tax amount |
| `data.total` | float | Final total |
| `data.payment_method` | string | VISA, MASTERCARD, etc. |
| `data.card_last_4` | string | Last 4 digits of card |
| `data.item_count` | integer | Number of items extracted |
| `sheet_update.rows_added` | integer | Rows added to sheet |
| `sheet_update.cells_updated` | integer | Cells modified |

---

**Response (Error - 400):**

```json
{
  "detail": "File must be an image!"
}
```

**Error Cases:**
- Non-image file uploaded
- Empty file
- Corrupted image
- File too large (>10MB)

---

**Response (Error - 401):**

```json
{
  "detail": "Unauthorized"
}
```

**Cause:** Invalid or missing authorization header (when authentication is enabled)

---

**Response (Error - 500):**

```json
{
  "detail": "Internal server error: <error message>"
}
```

**Error Cases:**
- Claude API failure
- Google Sheets API failure
- Parsing error
- Network timeout

---

## Data Extraction Details

### What Gets Extracted

The API extracts the following information from receipts:

**Receipt-Level Data:**
- Store name and location
- Transaction ID/receipt number
- Transaction date
- Payment method and card details
- Subtotal, tax, and total amounts

**Item-Level Data:**
- Product name (exactly as shown)
- Quantity purchased
- Unit price (price per item)
- Line total (quantity × unit price)
- Itemized tax (if available)

### Quantity Detection

The system intelligently distinguishes between quantities and size indicators:

**Quantities (extracted):**
- "5 @" or "5@" → quantity = 5
- "3x" or "3 ×" → quantity = 3
- "QTY 2" → quantity = 2
- "2 BANANAS" → quantity = 2

**Size Indicators (NOT quantities):**
- "3Z" or "3OZ" → 3 ounces (quantity = 1)
- "16.9" → 16.9 oz (quantity = 1)
- "24P" → 24-pack (quantity = 1)
- "2CT" → 2-count package (quantity = 1)

### Excluded Items

These line items are NOT included as products:
- BOTTLE DEPOSIT / CRV
- BAG FEE
- COUPON / DISCOUNT
- Tax lines
- Payment/tender lines

---

## Google Sheets Integration

### Sheet Structure

Each receipt creates multiple rows in Google Sheets:

**Header Row:**
```
Receipt ID | Timestamp | Store Name | Store Address | Receipt Date | 
Item Name | Unit Price | Quantity | Tax | Item Price | Payment Method | Card Last 4
```

**Data Rows:**
- One row per item
- Final row with "Total" in Item Name column
- All rows share the same Receipt ID

**Example:**
```
3743 | 2025-12-08 04:48 | CVS PHARMACY | 11831 Hawthorne Blvd | 2023-01-10 | 
BL SNTV 50 LTN 3Z | 11.69 | 1 | | 11.69 | VISA | 9284

3743 | 2025-12-08 04:48 | CVS PHARMACY | 11831 Hawthorne Blvd | 2023-01-10 | 
CAPILO JOJOBA OIL 4Z | 3.99 | 1 | | 3.99 | VISA | 9284

3743 | 2025-12-08 04:48 | CVS PHARMACY | 11831 Hawthorne Blvd | 2023-01-10 | 
Total | | | 6.48 | 64.88 | VISA | 9284
```

### Querying the Data

**Find all items from a specific receipt:**
```sql
=QUERY(A:L, "SELECT * WHERE A = '3743'")
```

**Total spending by store:**
```sql
=QUERY(A:L, "SELECT C, SUM(J) WHERE E = 'Total' GROUP BY C")
```

**All receipts from December 2025:**
```sql
=QUERY(A:L, "SELECT * WHERE E >= DATE '2025-12-01' AND E < DATE '2026-01-01'")
```

---

## Rate Limits

### Claude API Limits
- **Tier 1:** 50 requests/minute
- **Tier 2:** 1,000 requests/minute
- **Tier 3:** 2,000 requests/minute

See [Anthropic Rate Limits](https://docs.anthropic.com/claude/reference/rate-limits)

### Google Sheets API Limits
- **Read Requests:** 300 per minute per project
- **Write Requests:** 60 per minute per user

See [Google Sheets API Quotas](https://developers.google.com/sheets/api/limits)

### Cloud Run Limits
- **Concurrency:** 80 requests per instance (default)
- **Timeout:** 60 seconds (configurable)
- **Memory:** 512MB (configurable)

---

## Error Handling

### Client Errors (4xx)

| Status Code | Meaning | Action |
|-------------|---------|--------|
| 400 | Bad Request | Check file format and size |
| 401 | Unauthorized | Verify API key |
| 413 | Payload Too Large | Reduce image size |
| 415 | Unsupported Media Type | Use JPG, PNG, or HEIC |

### Server Errors (5xx)

| Status Code | Meaning | Action |
|-------------|---------|--------|
| 500 | Internal Server Error | Retry request |
| 502 | Bad Gateway | Cloud Run issue, retry |
| 503 | Service Unavailable | Temporary outage, retry |
| 504 | Gateway Timeout | Image processing took too long |

### Retry Strategy

```python
import time
import requests

def upload_receipt_with_retry(file_path, max_retries=3):
    for attempt in range(max_retries):
        try:
            files = {"file": open(file_path, "rb")}
            response = requests.post(
                "https://your-url.run.app/receipt",
                files=files,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

---

## Performance

### Expected Latency

| Operation | Time |
|-----------|------|
| Image upload | < 1s |
| Claude Vision processing | 2-3s |
| Google Sheets update | < 1s |
| **Total end-to-end** | **3-5s** |

### Optimization Tips

1. **Image Size:** Smaller images process faster
   - Recommended: < 2MB
   - System auto-compresses to 4MB

2. **Concurrent Requests:** Batch processing
   - Use async requests for multiple receipts
   - Respect rate limits

3. **Regional Deployment:** Deploy close to users
   - `us-central1` for USA
   - `europe-west1` for Europe
   - `asia-northeast1` for Asia

---

## Security

### API Key Management

**Never commit API keys to version control!**

Use environment variables:
```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxx
export GOOGLE_CREDS_JSON='{"type":"service_account",...}'
```

Or use secret managers:
- Google Cloud Secret Manager
- AWS Secrets Manager
- HashiCorp Vault

### Data Privacy

**What we store:**
- Extracted receipt data (text only)
- No images are stored by default

**What we don't store:**
- Credit card numbers (only last 4 digits)
- Full account numbers
- Personal identification data

### HTTPS Only

All API endpoints use HTTPS encryption. HTTP requests are automatically redirected to HTTPS.

---

## Webhook Support (Coming Soon)

Future support for asynchronous processing:

```json
POST /receipt
{
  "file": "<image>",
  "webhook_url": "https://your-callback-url.com/webhook",
  "metadata": {
    "user_id": "123",
    "category": "groceries"
  }
}
```

Callback payload:
```json
{
  "receipt_id": "3743",
  "status": "success",
  "data": { ... },
  "metadata": { ... }
}
```

---

## SDK Examples

### Python SDK

```python
import requests
from pathlib import Path

class ReceiptOCR:
    def __init__(self, api_url, api_key=None):
        self.api_url = api_url
        self.api_key = api_key
    
    def process_receipt(self, image_path):
        """Process a receipt image"""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        with open(image_path, "rb") as f:
            files = {"file": (Path(image_path).name, f, "image/jpeg")}
            response = requests.post(
                f"{self.api_url}/receipt",
                headers=headers,
                files=files,
                timeout=30
            )
        
        response.raise_for_status()
        return response.json()

# Usage
client = ReceiptOCR("https://your-url.run.app", "YOUR_API_KEY")
result = client.process_receipt("receipt.jpg")
print(f"Processed {result['data']['store_name']}: ${result['data']['total']}")
```

### JavaScript SDK

```javascript
class ReceiptOCR {
  constructor(apiUrl, apiKey = null) {
    this.apiUrl = apiUrl;
    this.apiKey = apiKey;
  }

  async processReceipt(file) {
    const formData = new FormData();
    formData.append('file', file);

    const headers = {};
    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }

    const response = await fetch(`${this.apiUrl}/receipt`, {
      method: 'POST',
      headers: headers,
      body: formData
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }
}

// Usage
const client = new ReceiptOCR('https://your-url.run.app', 'YOUR_API_KEY');
const result = await client.processReceipt(fileInput.files[0]);
console.log(`Processed ${result.data.store_name}: $${result.data.total}`);
```

---

## Testing

### Test Receipts

Sample receipts are provided in `tests/test_receipts/`:
- `cvs_sample.jpg` - Pharmacy receipt
- `target_sample.jpg` - Retail receipt
- `traderjoes_sample.jpg` - Grocery receipt

### Unit Tests

```bash
pytest tests/test_api.py -v
```

### Integration Tests

```bash
pytest tests/test_integration.py -v
```

### Load Testing

```bash
# Install locust
pip install locust

# Run load test
locust -f tests/load_test.py --host=https://your-url.run.app
```

---

## Support

**Issues:** [GitHub Issues](https://github.com/yourusername/receipt-ocr/issues)  
**Discussions:** [GitHub Discussions](https://github.com/yourusername/receipt-ocr/discussions)  
**Email:** your-email@example.com

---

## Changelog

### v3.0.0 (2025-12-08)
- Added universal store support
- Added address extraction
- Fixed quantity vs. size detection
- Improved item extraction accuracy to 94%
- Added comprehensive documentation

### v2.0.0 (2025-11-15)
- Added Google Sheets integration
- Implemented iPhone Shortcuts support
- Added image compression

### v1.0.0 (2025-10-01)
- Initial release
- Basic OCR functionality
- Claude Vision integration

---

**Last Updated:** December 8, 2025  
**API Version:** 3.0