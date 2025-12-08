"""
Enhanced parser - extracts quantity, unit price, and taxes
"""
import os
import base64
import json
from datetime import datetime
from PIL import Image
import io

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def compress_image_smart(image_bytes: bytes) -> bytes:
    """Smart compression that maintains text readability"""
    target_size = 4 * 1024 * 1024
    
    if len(image_bytes) <= target_size:
        print(f"   ✓ Image OK: {len(image_bytes) / 1024 / 1024:.2f} MB")
        return image_bytes
    
    print(f"   📦 Compressing: {len(image_bytes) / 1024 / 1024:.2f} MB")
    
    image = Image.open(io.BytesIO(image_bytes))
    
    if image.mode in ('RGBA', 'P', 'LA'):
        image = image.convert('RGB')
    
    ratio = (target_size / len(image_bytes)) ** 0.5
    new_size = (int(image.width * ratio * 0.95), int(image.height * ratio * 0.95))
    image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    output = io.BytesIO()
    image.save(output, format='JPEG', quality=92, optimize=True)
    
    result = output.getvalue()
    print(f"   ✓ Compressed: {len(result) / 1024 / 1024:.2f} MB")
    return result


def parse_receipt_image(image_bytes: bytes) -> dict:
    """Parse receipt with enhanced item details including quantity and tax"""
    
    image_bytes = compress_image_smart(image_bytes)
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = """
    You are an expert at reading receipts from ANY store (Target, Walmart, CVS, Trader Joe's, Costco, Grocery stores, restuarants, Pharmacies, etc.)
    
    Carefully analyze this receipt and extract ALL information.

=== STEP 1: STORE & LOCATION INFO ===
Extract:
- Store name (e.g., "TARGET", "CVS PHARMACY", "TRADER JOE'S", "WALMART")
- Full address including:
  * Street address (e.g., "11831 HAWTHORNE BLVD")
  * City
  * State
  * ZIP code
  * Phone number (if shown)

Combine into one address string like: "11831 Hawthorne Blvd, Hawthorne, CA 90250"

=== STEP 2: TRANSACTION INFO ===
Look for (labels vary by store):
- Receipt/Transaction ID: 
  * Target: Look for transaction numbers
  * CVS: "TRN#", "TRANS"
  * Walmart: "TC#" 
  * Others: Any transaction/receipt identifier
  
- Date: Can be in various formats (MM/DD/YY, YYYY-MM-DD, DD/MM/YYYY)
  Convert to YYYY-MM-DD format
  
- Payment info:
  * Method: VISA, MASTERCARD, AMEX, DISCOVER, DEBIT, CASH, APPLE PAY, etc.
  * Card last 4 digits (look for ****1234 or similar patterns)

=== STEP 3: EXTRACT ALL ITEMS ===

**CRITICAL: Read EVERY line item on the receipt. Do not skip any items.**

For EACH item, extract:
- **name**: Product name EXACTLY as shown (even if abbreviated)
- **quantity**: The number of items purchased
- **unit_price**: Price per single item  
- **line_total**: Total for this line (quantity × unit_price)

**HOW TO IDENTIFY QUANTITY:**

✅ ACTUAL QUANTITIES (extract these):
- "5 @" or "5@" → quantity = 5
- "3 x" or "3x" → quantity = 3  
- "QTY 2" → quantity = 2
- "2 BANANAS" (number before product name) → quantity = 2
- If nothing indicates multiple items → quantity = 1

❌ SIZE/WEIGHT INDICATORS (these are NOT quantities):
- "3Z", "3OZ", "4OZ" = size in ounces → quantity = 1
- "16.9", "16.9oz" = size → quantity = 1
- "24P", "24PK" = package size (24-pack) → quantity = 1
- "2CT" = item comes in 2-count package → quantity = 1
- "1.5LB", "0.5KG" = weight → quantity = 1
- Any measurement unit → quantity = 1

**EXAMPLES:**

Receipt Line: "BL SNTV 50 LTN 3Z    11.69"
→ {"name": "BL SNTV 50 LTN 3Z", "quantity": 1, "unit_price": 11.69, "line_total": 11.69}
Why? 3Z is the SIZE (3 ounces), not quantity

Receipt Line: "ONIONS RED 5 @ 1.19"  
→ {"name": "ONIONS RED", "quantity": 5, "unit_price": 1.19, "line_total": 5.95}
Why? "5 @" means 5 items at $1.19 each

Receipt Line: "CVS PURFD WTR 24P 16.9    5.99"
→ {"name": "CVS PURFD WTR 24P 16.9", "quantity": 1, "unit_price": 5.99, "line_total": 5.99}
Why? 24P (24-pack) and 16.9 (oz) are SIZE indicators

Receipt Line: "BANANAS 3 @ $0.29"
→ {"name": "BANANAS", "quantity": 3, "unit_price": 0.29, "line_total": 0.87}

Receipt Line: "MILK GALLON    3.99"
→ {"name": "MILK GALLON", "quantity": 1, "unit_price": 3.99, "line_total": 3.99}

**ITEMS TO EXCLUDE (not products):**
- "BOTTLE DEPOSIT", "CRV", "BAG FEE"
- "COUPON", "DISCOUNT" 
- Tax lines (but extract tax amount separately)
- Payment/tender lines

=== STEP 4: TOTALS ===
Extract (labels vary by store):
- Subtotal: Pre-tax amount ("SUBTOTAL", "SUB TOTAL", "MERCHANDISE")
- Tax: Tax amount ("TAX", "SALES TAX", "CA TAX", "STATE TAX")  
- Total: Final amount ("TOTAL", "AMOUNT DUE", "BALANCE DUE")

=== OUTPUT FORMAT ===

Return ONLY valid JSON (no other text):

{
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
    "items": [
        {
            "name": "BL SNTV 50 LTN 3Z",
            "quantity": 1,
            "unit_price": 11.69,
            "line_total": 11.69
        },
        {
            "name": "ONIONS RED",
            "quantity": 5,
            "unit_price": 1.19,
            "line_total": 5.95
        }
    ]
}

**IMPORTANT REMINDERS:**
1. Extract EVERY single item - count them first
2. Product names: Copy EXACTLY as shown (abbreviations and all)
3. Quantity defaults to 1 unless explicitly stated otherwise
4. Sizes/weights are NOT quantities
5. Include full address with street, city, state, ZIP
6. Double-check you didn't miss any items

Now analyze this receipt and return complete JSON.
"""

    try:
        print("🔍 Analyzing with Claude Vision...")
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_base64,
                        },
                    },
                    {"type": "text", "text": prompt}
                ],
            }],
        )
        
        response_text = message.content[0].text.strip()
        
        # Extract JSON
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end if end != -1 else None].strip()
        elif response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
        
        parsed_data = json.loads(response_text.strip())
        
        # Set defaults
        parsed_data.setdefault("receipt_id", datetime.now().strftime("%Y%m%d%H%M%S"))
        parsed_data.setdefault("store_name", None)
        parsed_data.setdefault("date", None)
        parsed_data.setdefault("address", None)
        parsed_data.setdefault("phone", None)
        parsed_data.setdefault("date", None)
        parsed_data.setdefault("subtotal", None)
        parsed_data.setdefault("tax", None)
        parsed_data.setdefault("total", None)
        parsed_data.setdefault("payment_method", None)
        parsed_data.setdefault("card_last_4", None)
        parsed_data.setdefault("items", [])
        
        # Validate items
        valid_items = []
        for item in parsed_data["items"]:
            if item.get("name") and item.get("line_total"):
                item.setdefault("quantity", 1)
                item.setdefault("unit_price", item.get("line_total"))
                valid_items.append(item)
        
        parsed_data["items"] = valid_items
        
        print(f"\n📝 Items extracted:")
        for idx, item in enumerate(valid_items, 1):
            qty = item.get('quantity', 1)
            unit_price = item.get('unit_price', 0)
            line_total = item.get('line_total', 0)
            if qty > 1:
                print(f"   {idx}. {item['name']}: {qty} × ${unit_price} = ${line_total}")
            else:
                print(f"   {idx}. {item['name']}: ${line_total}")
        
        return parsed_data
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "receipt_id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "store_name": None,
            "address": None,
            "phone": None,
            "date": None,
            "subtotal": None,
            "tax": None,
            "total": None,
            "payment_method": None,
            "card_last_4": None,
            "items": [],
        }

if __name__ == "__main__":
    # Test with any receipt
    import sys
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        print(f"\n🧪 Testing universal parser with: {image_path}\n")
        
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        result = parse_receipt_image(image_bytes)
        
        print("\n" + "="*70)
        print("FULL PARSED RESULT:")
        print("="*70)
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python universal_parser.py <image_path>")





