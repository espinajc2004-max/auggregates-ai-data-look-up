"""
Hugging Face Spaces entry point.
HF Spaces expects app.py at root with a Gradio or FastAPI app.
We expose our FastAPI app here.
"""
import os
from app.main import app  # noqa: F401 — HF Spaces picks this up via uvicorn
