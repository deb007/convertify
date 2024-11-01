# app.py
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional
import uvicorn
import os
from pathlib import Path
import uuid
from datetime import datetime, timedelta
import shutil
import asyncio
from pydantic import BaseModel

# Import the document converter classes
from converter import DocumentConverter, DocxReader, MarkdownWriter

# Create FastAPI app
app = FastAPI(
    title="Document Converter API",
    description="API for converting documents between different formats",
    version="1.0.0"
)

# Configure upload and converted files directories
UPLOAD_DIR = Path("uploads")
CONVERTED_DIR = Path("converted")
UPLOAD_DIR.mkdir(exist_ok=True)
CONVERTED_DIR.mkdir(exist_ok=True)

# Initialize the document converter
converter = DocumentConverter()

class ConversionResponse(BaseModel):
    """Response model for conversion status"""
    message: str
    conversion_id: str
    status: str

class ConversionStatus(BaseModel):
    """Model for conversion status"""
    conversion_id: str
    status: str
    input_file: str
    output_file: Optional[str] = None
    created_at: datetime

# Store conversion statuses
conversion_statuses = {}

async def cleanup_old_files():
    """Cleanup files older than 1 hour"""
    while True:
        current_time = datetime.now()
        # Clean up files older than 1 hour
        for directory in [UPLOAD_DIR, CONVERTED_DIR]:
            for file_path in directory.glob("*"):
                if file_path.is_file():
                    file_age = current_time - datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_age > timedelta(hours=1):
                        file_path.unlink()
        
        # Clean up old conversion statuses
        expired_conversions = [
            conv_id for conv_id, status in conversion_statuses.items()
            if (current_time - status.created_at) > timedelta(hours=1)
        ]
        for conv_id in expired_conversions:
            conversion_statuses.pop(conv_id)
        
        await asyncio.sleep(3600)  # Run every hour

@app.on_event("startup")
async def startup_event():
    """Start background cleanup task"""
    asyncio.create_task(cleanup_old_files())

@app.post("/convert/", response_model=ConversionResponse)
async def convert_document(
    file: UploadFile,
    output_format: str = ".md"
):
    """
    Convert uploaded document to specified format
    Currently supports:
    - Input: .docx
    - Output: .md
    """
    # Validate input format
    input_extension = Path(file.filename).suffix.lower()
    if input_extension not in converter.readers:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported input format: {input_extension}"
        )
    
    # Validate output format
    if output_format not in converter.writers:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported output format: {output_format}"
        )
    
    # Generate unique ID for this conversion
    conversion_id = str(uuid.uuid4())
    
    # Save uploaded file
    input_path = UPLOAD_DIR / f"{conversion_id}{input_extension}"
    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Generate output path
    output_path = CONVERTED_DIR / f"{conversion_id}{output_format}"
    
    # Store conversion status
    conversion_statuses[conversion_id] = ConversionStatus(
        conversion_id=conversion_id,
        status="processing",
        input_file=file.filename,
        created_at=datetime.now()
    )
    
    try:
        # Perform conversion
        converter.convert(str(input_path), str(output_path))
        
        # Update conversion status
        conversion_statuses[conversion_id].status = "completed"
        conversion_statuses[conversion_id].output_file = output_path.name
        
        return ConversionResponse(
            message="Document conversion started",
            conversion_id=conversion_id,
            status="success"
        )
    
    except Exception as e:
        # Update conversion status
        conversion_statuses[conversion_id].status = "failed"
        
        # Clean up files
        if input_path.exists():
            input_path.unlink()
        if output_path.exists():
            output_path.unlink()
        
        raise HTTPException(
            status_code=500,
            detail=f"Conversion failed: {str(e)}"
        )

@app.get("/status/{conversion_id}", response_model=ConversionStatus)
async def get_conversion_status(conversion_id: str):
    """Get the status of a conversion"""
    if conversion_id not in conversion_statuses:
        raise HTTPException(
            status_code=404,
            detail="Conversion ID not found"
        )
    
    return conversion_statuses[conversion_id]

@app.get("/download/{conversion_id}")
async def download_converted_file(conversion_id: str):
    """Download the converted file"""
    # Check if conversion exists and is completed
    if conversion_id not in conversion_statuses:
        raise HTTPException(
            status_code=404,
            detail="Conversion ID not found"
        )
    
    status = conversion_statuses[conversion_id]
    if status.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Conversion is not completed. Current status: {status.status}"
        )
    
    output_file = CONVERTED_DIR / status.output_file
    if not output_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Converted file not found"
        )
    
    return FileResponse(
        path=output_file,
        filename=f"converted_{status.input_file}{Path(status.output_file).suffix}",
        media_type="application/octet-stream"
    )

@app.get("/supported-formats")
async def get_supported_formats():
    """Get list of supported input and output formats"""
    return {
        "input_formats": list(converter.readers.keys()),
        "output_formats": list(converter.writers.keys())
    }

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
