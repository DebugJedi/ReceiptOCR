from fastapi import FastAPI, File, UploadFile, HTTPException, Header
from fastapi.responses import JSONResponse
import uvicorn
import io
from PIL import Image
from config import system_API
from parser import parse_text
from gsheet import append_to_sheet
import easyocr

app = FastAPI()
reader = easyocr.Reader(['en'])

@app.post("/receipt")
async def process_receipt(
    file: UploadFile = File(...),
    authorization: str | None = Header(None)
):
    if authorization != f"{system_API}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    image_bytes = await file.read()
    image_stream = io.BytesIO(image_bytes)
    image = Image.open(image_stream)

    result = reader.readtext(image_bytes, detail=0)
    raw_text = "\n".join(result)

    parsed = parse_text(raw_text)

    append_to_sheet(parsed)

    return JSONResponse({"status": "ok", "parsed": parsed})

