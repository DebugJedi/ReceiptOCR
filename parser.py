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
    
    prompt = """Analyze this receipt and extract ALL information as JSON.

EXTRACT THESE FIELDS:
- receipt_id: Transaction number (look for "TRANS" near bottom)
- store_name: Store name at top
- date: Date in YYYY-MM-DD format
- subtotal: Amount before tax (if shown)
- tax: Tax amount
- total: Final total
- payment_method: VISA/MASTERCARD/etc
- card_last_4: Last 4 digits of card

FOR EACH ITEM, EXTRACT:
- name: Item name exactly as shown
- quantity: Number of items (default 1 if not specified)
- unit_price: Price per single unit
- line_total: Total for this line (quantity × unit_price)

IMPORTANT:
- For items like "5 @ $1.19", quantity=5, unit_price=1.19, line_total=5.95
- For items like "8 @ $0.29", quantity=8, unit_price=0.29, line_total=2.32
- For single items, quantity=1, unit_price and line_total are the same
- Look for tax line (usually shows "Tax: $X.XX @ X.XX%")

Return ONLY valid JSON:
{
    "receipt_id": "56594",
    "store_name": "TRADER JOE'S",
    "date": "2025-11-20",
    "subtotal": 26.76,
    "tax": 0.37,
    "total": 27.13,
    "payment_method": "VISA",
    "card_last_4": "8728",
    "items": [
        {
            "name": "CAULIFLOWER EACH",
            "quantity": 1,
            "unit_price": 2.99,
            "line_total": 2.99
        },
        {
            "name": "ONIONS RED JUMBO EACH",
            "quantity": 5,
            "unit_price": 1.19,
            "line_total": 5.95
        }
    ]
}"""

    try:
        print("🔍 Analyzing with Claude Vision...")
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
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
        
        print(f"✅ Extracted: {parsed_data.get('store_name')} - {len(valid_items)} items")
        print(f"   Subtotal: ${parsed_data.get('subtotal')} | Tax: ${parsed_data.get('tax')} | Total: ${parsed_data.get('total')}")
        
        return parsed_data
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "receipt_id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "store_name": None,
            "date": None,
            "subtotal": None,
            "tax": None,
            "total": None,
            "payment_method": None,
            "card_last_4": None,
            "items": [],
        }