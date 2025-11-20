"""
Hybrid parser: Uses OCR text + Vision API for best accuracy
"""
import os
from dotenv import load_dotenv
import anthropic
import json
from datetime import datetime

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def parse_with_ocr_text(ocr_text: str) -> dict:
    """
    Use Claude to parse OCR text with strict accuracy requirements.
    """
    
    prompt = f"""You are analyzing OCR-extracted text from a receipt. Extract ACCURATE information.

CRITICAL RULES:
1. Use ONLY the information present in the text below
2. DO NOT invent or guess any data
3. Item prices are usually at the end of each line (after $)
4. Watch for "2 @ $3.99" which means 2 items at $3.99 each
5. Verify the total matches approximately the sum of items

OCR TEXT:
{ocr_text}

Extract and return ONLY this JSON (no other text):
{{
    "receipt_id": "transaction number from receipt",
    "store_name": "store name",
    "date": "YYYY-MM-DD",
    "total": 0.00,
    "payment_method": "VISA/MASTERCARD/etc",
    "card_last_4": "last 4 digits",
    "items": [
        {{"name": "exact item name", "price": 0.00}}
    ]
}}

If you cannot determine a value, use null."""

    try:
        print("🔍 Parsing OCR text with AI...")
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = message.content[0].text.strip()
        
        print(f"\n🤖 AI Response:\n{response_text}\n")
        
        # Extract JSON
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            if end == -1:
                response_text = response_text[start:].strip()
            else:
                response_text = response_text[start:end].strip()
        elif response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
        
        response_text = response_text.strip()
        
        parsed_data = json.loads(response_text)
        
        # Ensure all expected fields exist
        parsed_data.setdefault("receipt_id", None)
        parsed_data.setdefault("store_name", None)
        parsed_data.setdefault("date", None)
        parsed_data.setdefault("total", None)
        parsed_data.setdefault("payment_method", None)
        parsed_data.setdefault("card_last_4", None)
        parsed_data.setdefault("items", [])
        
        # Generate fallback receipt ID if none found
        if not parsed_data["receipt_id"]:
            parsed_data["receipt_id"] = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Validate items
        valid_items = []
        for item in parsed_data.get("items", []):
            if item.get("price") and item.get("price") > 0 and item.get("name"):
                valid_items.append(item)
        
        parsed_data["items"] = valid_items
        
        print(f"✅ Parsed successfully:")
        print(f"   Receipt ID: {parsed_data.get('receipt_id')}")
        print(f"   Store: {parsed_data.get('store_name')}")
        print(f"   Date: {parsed_data.get('date')}")
        print(f"   Total: ${parsed_data.get('total')}")
        print(f"   Payment: {parsed_data.get('payment_method')} {parsed_data.get('card_last_4')}")
        print(f"   Valid items: {len(valid_items)}")
        
        if valid_items:
            print(f"\n   Items extracted:")
            for item in valid_items:
                print(f"      • {item['name']}: ${item['price']}")
        print()
        
        return parsed_data
        
    except Exception as e:
        print(f"❌ Hybrid parsing error: {e}\n")
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