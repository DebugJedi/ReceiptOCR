import os,json, tempfile
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime


load_dotenv()

SPREADSHEET_ID = os.getenv("spreadsheet_id")

BASE_DIR = Path(__file__).resolve().parent

google_cred = os.getenv("GOOGLE_CREDS_JSON")
if google_cred:
    try:
        cred_dict = json.loads(google_cred)
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix='.json', delete=False)
        json.dump(cred_dict, temp_file)
        temp_file.close()
        CREDENTIALS_PATH = Path(temp_file.name)
        print(f"☑️ Using GOOGLE_CREDS_JSON from environment")
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse GOOGLE_CREDS_JSON: {e}" )
        CREDENTIALS_PATH = None
else:
    env_cred = os.getenv("GOOGLE_CREDS_PATH")
    if env_cred:
        CREDENTIALS_PATH = Path(env_cred)
        if not CREDENTIALS_PATH.is_absolute():
            CREDENTIALS_PATH = BASE_DIR / CREDENTIALS_PATH
    else:
        CREDENTIALS_PATH = BASE_DIR / "secrets" / "receipt-credentials.json"
    print(f"✅ Using credentials file: {CREDENTIALS_PATH}")

    

SHEET_NAME = "Reciepts"


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# New header with itemized structure
HEADER_ROW = [
    "Receipt ID",
    "Timestamp", 
    "Store Name", 
    "Receipt Date", 
    "Item Name", 
    "Item Price", 
    "Payment Method",
    "Card Last 4",
    "Receipt Total",
    "Raw Text"
]


def get_service():
    """Initialize and return Google Sheets API service"""
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(f"Credential file not found at: {CREDENTIALS_PATH}")
    
    if not SPREADSHEET_ID:
        raise ValueError(
            "SPREADSHEET_ID not found in environment variables.\n"
            "Please add it to your .env file."
        )
    
    creds = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=SCOPES)
    
    return build("sheets", "v4", credentials=creds)


def ensure_header(service):
    """Ensure the sheet has the correct header row"""
    range_ = f"{SHEET_NAME}!A1:J1"  # 10 columns now
    
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=range_,
        ).execute()

        values = result.get("values", [])
        
        if not values:
            print("📝 No header found, creating header row...")
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A1",
                valueInputOption="RAW",
                body={"values": [HEADER_ROW]},
            ).execute()
            print("✅ Header created")
        else:
            print("✓ Header already present:", values[0])

    except Exception as e:
        print(f"⚠️ Error checking/creating header: {e}")
        raise


def append_to_sheet(data: dict):
    """
    Append parsed receipt data to Google Sheets.
    Creates ONE ROW PER ITEM for detailed tracking.

    Args: 
        data: Dict containing receipt_id, store_name, date, total, items, 
              payment_method, card_last_4, raw_text

    Return:
        API response from the append operation
    """
    print(f"\n📊 Processing receipt: {data.get('receipt_id')}")
    
    service = get_service()
    ensure_header(service)

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Extract common receipt info
    receipt_id = data.get("receipt_id") or "UNKNOWN"
    store_name = data.get("store_name") or "Unknown Store"
    receipt_date = data.get("date") or ""
    total = data.get("total") or ""
    payment_method = data.get("payment_method") or ""
    card_last_4 = data.get("card_last_4") or ""
    raw_text = data.get("raw_text") or ""
    items = data.get("items", [])
    
    print(f"📝 Receipt Info:")
    print(f"   Receipt ID: {receipt_id}")
    print(f"   Store: {store_name}")
    print(f"   Date: {receipt_date}")
    print(f"   Total: ${total}")
    print(f"   Payment: {payment_method} {card_last_4}")
    print(f"   Items: {len(items)}")
    
    # Create one row per item
    values = []
    
    if items and len(items) > 0:
        # One row for each item
        for idx, item in enumerate(items, 1):
            item_name = item.get("name", "").strip()
            item_price = item.get("price")
            
            # Skip items without valid name or price
            if not item_name:
                print(f"   ⚠️  Skipping item without name")
                continue
            
            # Convert None to 0 or skip if price is invalid
            if item_price is None:
                print(f"   ⚠️  Skipping item with no price: {item_name}")
                continue
            
            # Ensure price is a number
            try:
                item_price = float(item_price)
                if item_price <= 0:
                    print(f"   ⚠️  Skipping item with invalid price: {item_name} ${item_price}")
                    continue
            except (ValueError, TypeError):
                print(f"   ⚠️  Skipping item with invalid price: {item_name}")
                continue
            
            row = [
                receipt_id,
                timestamp,
                store_name,
                receipt_date,
                item_name,
                item_price,
                payment_method,
                card_last_4,
                
                raw_text if idx == 1 else "",  # Only include raw text on first item to save space
            ]
            values.append(row)
            print(f"      {idx}. {item_name}: ${item_price}")
        lst_row = [receipt_id, timestamp, store_name, receipt_date, "Total", total, payment_method, card_last_4]
        values.append(lst_row)
    else:
        # No items found - create one summary row
        print("   ⚠️  No items found, creating summary row")
        row = [
            receipt_id,
            timestamp,
            store_name,
            receipt_date,
            "No items detected",
            "",
            payment_method,
            card_last_4,
            total,
            raw_text,
        ]
        values.append(row)
    
    range_ = f"{SHEET_NAME}!A2"

    try:
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=range_,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
        
        rows_added = len(values)
        print(f"\n✅ Added {rows_added} row(s) to sheet")
        print(f"   Updated {result['updates']['updatedCells']} cells\n")
        return result
        
    except Exception as e:
        print(f"❌ Error appending to sheet: {e}")
        raise


if __name__ == "__main__":
    test_data = {
        "receipt_id": "TEST123",
        "store_name": "Test Store",
        "date": "2025-11-19",
        "total": 25.99,
        "payment_method": "VISA",
        "card_last_4": "1234",
        "items": [
            {"name": "Coffee - Large", "price": 4.50},
            {"name": "Turkey Sandwich", "price": 8.99},
            {"name": "Chips - BBQ", "price": 2.50},
            {"name": "Orange Juice", "price": 3.99},
            {"name": "Apple", "price": 1.25}
        ],
        "raw_text": "This is a test receipt with multiple items."
    }

    print("\n🧪 Testing Google Sheets integration with itemized rows...\n")
    append_to_sheet(test_data)
    print("✅ Test complete. Check your Google Sheet!")