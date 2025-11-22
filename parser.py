"""
Final optimized parser - uses Vision API with better compression and prompts
"""
import os
import base64

import anthropic
import json
from datetime import datetime
from PIL import Image
import io


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass



client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def compress_image_smart(image_bytes: bytes) -> bytes:
    """
    Smart compression that maintains text readability
    """
    # Target under 4 MB for safety (base64 adds ~33% overhead)
    target_size = 4 * 1024 * 1024
    
    if len(image_bytes) <= target_size:
        print(f"   ✓ Image OK: {len(image_bytes) / 1024 / 1024:.2f} MB")
        return image_bytes
    
    print(f"   📦 Compressing: {len(image_bytes) / 1024 / 1024:.2f} MB → 4 MB")
    
    image = Image.open(io.BytesIO(image_bytes))
    
    # Convert to RGB
    if image.mode in ('RGBA', 'P', 'LA'):
        image = image.convert('RGB')
    
    # Calculate resize ratio
    ratio = (target_size / len(image_bytes)) ** 0.5
    new_size = (int(image.width * ratio * 0.95), int(image.height * ratio * 0.95))
    
    print(f"   📐 Resize: {image.width}x{image.height} → {new_size[0]}x{new_size[1]}")
    
    image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Save with high quality
    output = io.BytesIO()
    image.save(output, format='JPEG', quality=92, optimize=True)
    
    result = output.getvalue()
    print(f"   ✓ Final: {len(result) / 1024 / 1024:.2f} MB")
    
    return result


def parse_receipt_image(image_bytes: bytes) -> dict:
    """
    Parse receipt using Claude Vision with optimized prompts
    """
    
    # Compress
    image_bytes = compress_image_smart(image_bytes)
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # Shorter, clearer prompt (saves tokens!)
    prompt = """Extract receipt data as JSON. Read carefully and use EXACT values from the image.

    

Format:
{
  "receipt_id": "trans number",
  "store_name": "store name",  
  "date": "YYYY-MM-DD",
  "subtotal": Amount before tax (if shown),
  tax: Tax amount,
  "total": Final total amount including taxes,
  "payment_method": "VISA",
  "card_last_4": "1234",
  "items": [
    {"name": "ITEM NAME", "unit price": 3.99, "itemized_tax": .65 (if shown), "quantity": 2, "price":7.98 }
  ]
}

Rules:
- Copy item names EXACTLY as shown
- Match each item to its price on the receipt
- If "Items in Transaction: 10" is shown, extract 10 items
- Use null if you cannot read something clearly
- For dates like "11-17-2025", convert to "2025-11-17"

Return only JSON, no other text."""

    try:
        print("🔍 Analyzing with Claude Vision...")
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,  # Reduced from 2000
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
        valid_items = [
            item for item in parsed_data["items"]
            if item.get("price") and item.get("price") > 0 and item.get("name")
        ]
        parsed_data["items"] = valid_items

        print(f"✅ Extracted: {parsed_data.get('store_name')} - {len(valid_items)} items - ${parsed_data.get('total')}")
        
        return parsed_data
        
    except anthropic.RateLimitError as e:
        print(f"⚠️  Rate limit hit. Wait 1 minute and try again.")
        print(f"   Error: {e}")
        return {
            "receipt_id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "store_name": "RATE_LIMIT_ERROR",
            "date": None,
            "total": None,
            "payment_method": None,
            "card_last_4": None,
            "items": [],
        }
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "receipt_id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "store_name": None,
            "date": None,
            "total": None,
            "payment_method": None,
            "card_last_4": None,
            "items": [],
        }