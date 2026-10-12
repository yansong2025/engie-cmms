import base64
import logging
import os
import sys

# Make the repo-root `analytics` package importable from the serverless bundle.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from analytics import AnalysisError, analyze, build_pdf, read_table

app = FastAPI()
logger = logging.getLogger(__name__)

# Vercel rejects request bodies over 4.5 MB before they reach this function.
MAX_FILE_BYTES = 4 * 1024 * 1024
DEFAULT_TARIFF = 0.15  # cost per kWh
DEFAULT_EMISSION_FACTOR = 0.4  # kg CO2e per kWh


# Deliberately sync: FastAPI runs it in a worker thread, keeping the CPU-bound
# parsing and rendering off the event loop.
@app.post("/api/analyze")
def analyze_utility_data(
    file: UploadFile = File(...),
    tariff: float = Form(DEFAULT_TARIFF, ge=0, le=1000),
    emission_factor: float = Form(DEFAULT_EMISSION_FACTOR, ge=0, le=100),
):
    file_bytes = file.file.read(MAX_FILE_BYTES + 1)
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File is too large. The limit is 4 MB.")

    try:
        raw = read_table(file_bytes, file.filename or "")
        analysis = analyze(raw, tariff=tariff, emission_factor=emission_factor)
        pdf_bytes = build_pdf(analysis)
    except AnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected failure analysing %r", file.filename)
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while analysing the file. Please try again.",
        ) from exc

    # The report goes straight back to the caller; nothing is stored server-side.
    return {
        **analysis.summary(),
        "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
    }
