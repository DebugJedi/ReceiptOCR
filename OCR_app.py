from fastapi import FastAPI, File, UploadFile, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import io, os
import logging
from dotenv import load_dotenv
from PIL import Image

# Import vision parser (the good one!)
from parser import parse_with_ocr_text
from gsheet import append_to_sheet

load_dotenv()

SYSTEM_API_KEY = os.getenv("system_API")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Receipt OCR API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "Receipt OCR API v3.0",
        "method": "Claude Vision API",
        "endpoints": {
            "POST /receipt": "Process receipt image (Vision + AI + Sheets)",
            "GET /": "Health check"
        }
    }

@app.post("/receipt")
async def process_receipt(
    file: UploadFile = File(...),
    authorization: str | None = Header(None)
):
    """
    Process a receipt image using Claude Vision API:
    1. Send image directly to Claude for analysis
    2. Extract structured data (items, prices, etc.)
    3. Append to Google Sheets
    """
    # Uncomment to enable authentication:
    # if authorization != f"Bearer {SYSTEM_API_KEY}":
    #     raise HTTPException(status_code=401, detail="Unauthorized")
    
    try: 
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="File must be an image!"
            )
        
        logger.info(f"📸 Processing receipt: {file.filename}")
        
        # Read image bytes
        image_bytes = await file.read()
        
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty file received.")
        
        # Verify it's a valid image
        try:
            image_stream = io.BytesIO(image_bytes)
            image = Image.open(image_stream)
            image.verify()
            logger.info("✓ Image validated")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image file: {str(e)}"
            )
        
        # Parse with Claude Vision - IMPORTANT: Pass image_bytes!
        logger.info("🤖 Analyzing receipt with Claude Vision...")
        parsed = parse_with_ocr_text(image_bytes)
        
        # Append to Google Sheets
        logger.info("📊 Appending to Google Sheets...")
        sheet_result = append_to_sheet(parsed)
        
        return JSONResponse({
            "status": "success",
            "message": "Receipt processed successfully",
            "data": {
                "receipt_id": parsed.get("receipt_id"),
                "store_name": parsed.get("store_name"),
                "date": parsed.get("date"),
                "total": parsed.get("total"),
                "payment_method": parsed.get("payment_method"),
                "card_last_4": parsed.get("card_last_4"),
                "item_count": len(parsed.get("items", [])),
            },
            "sheet_update": {
                "rows_added": sheet_result.get("updates", {}).get("updatedRows", 0),
                "cells_updated": sheet_result.get("updates", {}).get("updatedCells", 0)
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error processing receipt: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(
        "OCR_app:app", 
        host="0.0.0.0",  # Allow external connections (for iPhone)
        port=8000, 
        reload=True
    )