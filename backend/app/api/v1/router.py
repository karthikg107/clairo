"""API v1 router."""
from fastapi import APIRouter

from app.api.v1.endpoints import health, upload, ocr

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(upload.router)
router.include_router(ocr.router)
