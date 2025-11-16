import os, json, tempfile
from google.oauth2.service_account import Credentials
import gspread
from config import spreadsheet_id

CREDENTIALS_PATH = "/secrets/receipt-credentials.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = spreadsheet_id

creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes = SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

def append_to_sheet(data: dict):
    row = [
        data.get("store_name"),
        data.get("date"),
        data.get("total"),
        data.get("raw_text"),
    ]

    existing_values = sheet.get_all_values()
    if not existing_values:
        # Write header row once
        header = ["Store Name", "Date", "Total", "Raw Text"]
        sheet.append_row(header)

    sheet.append_row(row)