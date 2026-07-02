"""API v1 router."""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    analyse,
    billing,
    classify,
    consent,
    detect,
    health,
    ocr,
    quota,
    upload,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(upload.router)
router.include_router(ocr.router)
router.include_router(detect.router)
router.include_router(classify.router)
router.include_router(analyse.router)
router.include_router(consent.router)
router.include_router(quota.router)
router.include_router(billing.router)
