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
    You are an epxert OCR system that reads receipts for ANY store with PERECT accuracy.
    Your task: Extract ALL information from this receipt with 100% accuracy.
    
    CRITICAL RULES:
    1. Read EVERY character EXACTLY as printed - don't correct spelling
    2. Count items carefully - if receipt says "Item Count: 20" extract 20 Items
    3. Verify your subtotal matches by all the line_totals
    4. Read quantity indicators at the Start of each line
    
    =============== QUANTITY DETECTION PATTERN ==================================
    Look at the BEGININING of each item line for quantity:

    ✅ QUANTITY INDICATORS (these mean multiple items):
    **PATTERN 1: Number at start of line**
    - "2 FS LAYS CHIPS" -> quantity = 2
    - "1 MILK GALLON" -> quantity = 1

    **PATTERN 2: "@" symbol (items at price)**
    "5 @ $1.99" -> quantity = 5, unit_price = 1.99
    "3 @ $0.29/lb" -> quantity = 3, unit_price = 0.29
    "0.59 lb @ $1.99/lb -> quanity =  0.58, unit_price = 1.99/lb, total_price of item = 0.58*1.99==1.1542

    **PATTERN 3: "x" multiplicatoin**
    "3 x ITEM" -> quantity =3 
    "2 x @ $5.99" -> quantity = 2

    **PATTERN 4: Weight-based items **
    "1.43 lb @ $1.99/lb" -> quantity = 1.43, unit_price = 1.99
    "0.62 lb @ $2.99/lb" -> quantity = 0.62, unit_price = 2.99

    **PATTERN 5: Multiple of same item on separate lines**
    "SOMOSAS VEGETABLE $3.99"
    "SOMOSAS VEGETABLE $3.99"
    -> These are 2 SEPARATE line items (not quantity = 2)


    ❌ NOT QUANTITIES (these are size/weights):
    - "400G" = 400 grams (package size)
    - "52G" = 52 grams (package size)
    - "3L" = 3 liters (Container size)
    - "70z" = 70 ounces (size)
    - "36" at the end like " 1 FS HR MOTI CHOOR LADOO 36" -> quantity 1 and 36 counts in a package.
    - Any number followed by G, OZ, L, ML, KG, LB are weights/sizes

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

**SPECIAL ITEMS**
- TAX -> quantity = 1
- BAG FEE -> quantity = 1 (or actual number is shown like 4 @ $0.10)
- BOTTLE DEPOSIT -> quantity = 1


ITEM EXTRACTION - STEP BY STEP PROCESS

For each line on the receipt:

**STEP 1: STORE INFORMATION**
- Store name, address, phone, store number

**STEP 2: Transaction info**
- Receipt ID, date, time, cashier, terminal

**STEP 3: Extract all line Items**

For each charge on the receipt:

1. Product items:
```
   {
     "name": "FS HR GOBI PARATHA 400G",
     "quantity": 1,
     "unit_price": 5.99,
     "line_total": 5.99,
     "category": "product"
   }
   ```

2. Tax:
   ```
   {
     "name": "TAX",
     "quantity": 1,
     "unit_price": 6.48,
     "line_total": 6.48,
     "category": "tax"
   }
   ```

3. Bag Fee:
   ```
   {
     "name": "BAG FEE",
     "quantity": 4,
     "unit_price": 0.10,
     "line_total": 0.40,
     "category": "fee"
   }
   ```

4. Bottle Deposit:
   ```
   {
     "name": "BOTTLE DEPOSIT",
     "quantity": 1,
     "unit_price": 0.05,
     "line_total": 0.05,
     "category": "deposit"
   }
   ```

**STEP 4: Totals**
- Subtotal (products only, before tax/fees)
- Total (sum of ALL line items)

**STEP 5: Payment**
- Payment method, card info

═══════════════════════════════════════════════════════════════════════
EXAMPLES OF CORRECT PARSING
═══════════════════════════════════════════════════════════════════════

**Example 1: Whole Foods Receipt**
```
Receipt shows:
365WFM DISH SOAP        $3.49 T
CONTAINER DEPOSIT       $0.05
Subtotal:               $32.60
Net Sales:              $32.60
Tax:        6.25%       $1.69
Total:                  $34.29

Parse as:
{
  "items": [
    {"name": "365WFM DISH SOAP", "quantity": 1, "unit_price": 3.49, "line_total": 3.49, "category": "product"},
    {"name": "CONTAINER DEPOSIT", "quantity": 1, "unit_price": 0.05, "line_total": 0.05, "category": "deposit"},
    {"name": "TAX", "quantity": 1, "unit_price": 1.69, "line_total": 1.69, "category": "tax"}
  ],
  "subtotal": 32.60,
  "total": 34.29
}
```

**Example 2: Trader Joe's with Bag Fee**
```
Receipt shows:
SAMOSAS VEGETABLE      $3.99
BAG FEE
  4 @ $0.10            $0.40
Tax:     @ 6.25%       $0.03
Total                  $75.94

Parse as:
{
  "items": [
    {"name": "SAMOSAS VEGETABLE", "quantity": 1, "unit_price": 3.99, "line_total": 3.99, "category": "product"},
    {"name": "BAG FEE", "quantity": 4, "unit_price": 0.10, "line_total": 0.40, "category": "fee"},
    {"name": "TAX", "quantity": 1, "unit_price": 0.03, "line_total": 0.03, "category": "tax"}
  ],
  "subtotal": 75.51,  # products + fees only
  "total": 75.94      # includes tax
}
```

**Example 3: Star Market with Multiple Items**
```
Receipt shows:
STONYFIELD PLN         $4.99
WT 0.58 lb @ $1.99/lb  $1.15
TAX                    $0.00
**** BALANCE           $77.21

Parse as:
{
  "items": [
    {"name": "STONYFIELD PLN", "quantity": 1, "unit_price": 4.99, "line_total": 4.99, "category": "product"},
    {"name": "WT 0.58 lb @ $1.99/lb", "quantity": 1, "unit_price": 1.15, "line_total": 1.15, "category": "product", "notes": "weighted"},
    {"name": "TAX", "quantity": 1, "unit_price": 0.00, "line_total": 0.00, "category": "tax"}
  ],
  "subtotal": 77.21,
  "total": 77.21
}
```

═══════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════════════

Return ONLY valid JSON:

{
  "receipt_id": "282876",
  "store_name": "FOODLAND MARKET",
  "address": "2234 Massachusetts Avenue, Cambridge, MA",
  "phone": "(617) 349-0009",
  "date": "2025-12-15",
  "time": "19:14:58",
  "cashier": "Mhafuzzz",
  "items": [
    {
      "name": "FS HR GOBI PARATHA 400G",
      "quantity": 1,
      "unit_price": 5.99,
      "line_total": 5.99,
      "category": "product"
    },
    {
      "name": "TAX",
      "quantity": 1,
      "unit_price": 0.00,
      "line_total": 0.00,
      "category": "tax"
    }
  ],
  "subtotal": 95.60,
  "total": 95.60,
  "payment_method": "Credit Card",
  "card_last_4": null
}

═══════════════════════════════════════════════════════════════════════
VALIDATION BEFORE RETURNING
═══════════════════════════════════════════════════════════════════════

1. ✓ Sum of ALL line_totals = total (within $0.10)
2. ✓ All quantities are integers ≥ 1
3. ✓ All prices are ≥ 0 (including $0.00 for tax)
4. ✓ Every charge has a category: "product", "tax", "fee", "deposit"

NOW: Analyze this receipt and return ONLY valid JSON.
Remember: Include tax, fees, and deposits as line items!
"""

    try:
        print("🔍 Analyzing receipt with Claude Vision API...")
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
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
        json_text = extract_json_from_response(response_text)
        
        # Parse JSON
        parsed_data = json.loads(json_text)
        
        # Validate and enrich
        parsed_data = validate_and_enrich_v2(parsed_data)
        
        # Display summary
        display_parsing_summary_v2(parsed_data)
        
        return parsed_data
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parse Error: {e}")
        print(f"Response preview: {response_text[:500]}...")
        return create_empty_result()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return create_empty_result()


def extract_json_from_response(response_text: str) -> str:
    """Extract JSON from various response formats"""
    json_text = response_text.strip()
    
    # Remove markdown code blocks
    if "```json" in json_text:
        start = json_text.find("```json") + 7
        end = json_text.find("```", start)
        json_text = json_text[start:end if end != -1 else None].strip()
    elif json_text.startswith("```"):
        lines = json_text.split("\n")
        json_text = "\n".join(lines[1:-1]) if len(lines) > 2 else json_text
    
    # Find JSON object
    if not json_text.startswith("{"):
        start = json_text.find("{")
        end = json_text.rfind("}") + 1
        if start != -1 and end > start:
            json_text = json_text[start:end]
    
    return json_text


def validate_and_enrich_v2(data: Dict) -> Dict:
    """Validate and enrich - NEW VERSION with all items included"""
    
    # Set defaults
    data.setdefault("receipt_id", datetime.now().strftime("%Y%m%d%H%M%S"))
    data.setdefault("store_name", None)
    data.setdefault("address", None)
    data.setdefault("phone", None)
    data.setdefault("date", None)
    data.setdefault("time", None)
    data.setdefault("cashier", None)
    data.setdefault("subtotal", 0.0)
    data.setdefault("total", 0.0)
    data.setdefault("payment_method", None)
    data.setdefault("card_last_4", None)
    data.setdefault("items", [])
    
    # Validate items
    valid_items = []
    total_from_items = 0.0
    product_subtotal = 0.0
    
    for item in data["items"]:
        if not item.get("name"):
            continue
        
        # Ensure fields
        quantity = item.get("quantity", 1)
        line_total = item.get("line_total", 0.0)
        category = item.get("category", "product")
        
        # Auto-calculate unit_price
        if not item.get("unit_price") or item.get("unit_price") == 0:
            item["unit_price"] = round(line_total / quantity, 2) if quantity > 0 else line_total
        
        # Ensure types
        item["quantity"] = int(quantity)
        item["unit_price"] = float(item["unit_price"])
        item["line_total"] = float(line_total)
        item["category"] = category
        
        valid_items.append(item)
        total_from_items += line_total
        
        # Track product-only subtotal (excluding tax)
        if category in ["product", "fee", "deposit"]:
            product_subtotal += line_total
    
    data["items"] = valid_items
    data["item_count"] = len(valid_items)
    
    # Validate total = sum of all items
    receipt_total = float(data.get("total", 0))
    if abs(total_from_items - receipt_total) > 0.10:
        print(f"\n⚠️  WARNING: Total mismatch!")
        print(f"   Sum of all items: ${total_from_items:.2f}")
        print(f"   Receipt total: ${receipt_total:.2f}")
        print(f"   Difference: ${abs(total_from_items - receipt_total):.2f}")
    
    # Info: show breakdown
    tax_items = [i for i in valid_items if i.get("category") == "tax"]
    fee_items = [i for i in valid_items if i.get("category") in ["fee", "deposit"]]
    product_items = [i for i in valid_items if i.get("category") == "product"]
    
    total_tax = sum(i["line_total"] for i in tax_items)
    total_fees = sum(i["line_total"] for i in fee_items)
    total_products = sum(i["line_total"] for i in product_items)
    
    print(f"\n📊 BREAKDOWN:")
    print(f"   Products: ${total_products:.2f} ({len(product_items)} items)")
    print(f"   Fees/Deposits: ${total_fees:.2f} ({len(fee_items)} items)")
    print(f"   Tax: ${total_tax:.2f} ({len(tax_items)} items)")
    print(f"   TOTAL: ${total_from_items:.2f}")
    
    return data


def display_parsing_summary_v2(data: Dict):
    """Display formatted summary - includes all items"""
    print(f"\n{'='*80}")
    print(f"📊 RECEIPT PARSING SUMMARY")
    print(f"{'='*80}")
    print(f"Store:        {data.get('store_name', 'Unknown')}")
    print(f"Date:         {data.get('date', 'Unknown')}")
    print(f"Receipt ID:   {data.get('receipt_id', 'Unknown')}")
    print(f"Total Items:  {data.get('item_count', 0)}")
    print(f"Total:        ${data.get('total', 0):.2f}")
    print(f"Payment:      {data.get('payment_method', 'Unknown')}")
    
    print(f"\n📝 ALL LINE ITEMS (Products + Tax + Fees + Deposits):")
    print(f"{'-'*80}")
    print(f"{'#':<3} {'Item Name':<45} {'Qty':>3} {'Price':>8} {'Total':>9} {'Type':<10}")
    print(f"{'-'*80}")
    
    for idx, item in enumerate(data.get('items', []), 1):
        qty = item['quantity']
        unit_price = item['unit_price']
        line_total = item['line_total']
        name = item['name'][:44]
        category = item.get('category', 'product')
        
        if qty > 1:
            print(f"{idx:<3} {name:<45} {qty:>3} ${unit_price:>7.2f} ${line_total:>8.2f} {category:<10}")
        else:
            print(f"{idx:<3} {name:<45} {qty:>3}          ${line_total:>8.2f} {category:<10}")
    
    print(f"{'='*80}\n")


def create_empty_result() -> Dict:
    """Create empty result structure"""
    return {
        "receipt_id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "store_name": None,
        "address": None,
        "phone": None,
        "date": None,
        "time": None,
        "cashier": None,
        "subtotal": 0.0,
        "total": 0.0,
        "payment_method": None,
        "card_last_4": None,
        "items": [],
        "item_count": 0
    }


def batch_process_receipts(image_paths: List[str]) -> List[Dict]:
    """Process multiple receipts in batch"""
    results = []
    total = len(image_paths)
    
    print(f"\n{'='*80}")
    print(f"🔄 BATCH PROCESSING {total} RECEIPTS")
    print(f"{'='*80}\n")
    
    for idx, path in enumerate(image_paths, 1):
        print(f"\n[{idx}/{total}] Processing: {path}")
        print(f"{'-'*80}")
        
        try:
            with open(path, 'rb') as f:
                image_bytes = f.read()
            
            result = parse_receipt_image(image_bytes)
            results.append({
                "file": path,
                "success": True,
                "data": result
            })
            
        except Exception as e:
            print(f"❌ Failed to process {path}: {e}")
            results.append({
                "file": path,
                "success": False,
                "error": str(e)
            })
    
    # Summary
    successful = sum(1 for r in results if r["success"])
    print(f"\n{'='*80}")
    print(f"✅ Batch Complete: {successful}/{total} receipts processed successfully")
    print(f"{'='*80}\n")
    
    return results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Single receipt: python universal_parser_v2.py <image_path>")
        print("  Multiple receipts: python universal_parser_v2.py <image1> <image2> ...")
        sys.exit(1)
    
    image_paths = sys.argv[1:]
    
    if len(image_paths) == 1:
        # Single receipt
        print(f"\n🧪 Processing receipt: {image_paths[0]}\n")
        
        with open(image_paths[0], 'rb') as f:
            image_bytes = f.read()
        
        result = parse_receipt_image(image_bytes)
        
        print("\n" + "="*80)
        print("FULL JSON OUTPUT:")
        print("="*80)
        print(json.dumps(result, indent=2))
        
    else:
        # Batch processing
        results = batch_process_receipts(image_paths)
        
        # Save results
        output_file = f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"📁 Batch results saved to: {output_file}")
