import re 
from datetime import datetime

def parse_text(text: str) -> dict:
    date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d[2,4])', text)
    date = date_match.group(1) if date_match else None

    total_match = re.search(r'Total\s*[:\-]?\s*\$?(\d+\.\d{2})', text, re.IGNORECASE)
    total = float(total_match.group(1)) if total_match else None

    first_line = text.splitlines()[0].strip() if text.splitlines() else None

    return {
        "store_name": first_line,
        "date": date,
        "total": total,
        "raw_text": text,
    }