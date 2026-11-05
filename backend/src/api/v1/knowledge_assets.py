import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/knowledge-assets", tags=["Knowledge assets"])
ASSETS = Path(__file__).resolve().parents[3] / "data" / "knowledge_assets"


@router.get("/{filename}")
def get_asset(filename: str):
    if not re.fullmatch(r"(?:[a-f0-9]{64}|pirit-2f-manual)\.(?:pdf|png|jpg|jpeg|webp|gif|svg|tif|tiff|jp2)", filename):
        raise HTTPException(404, "Файл не найден")
    path = ASSETS / filename
    if not path.is_file():
        raise HTTPException(404, "Файл не найден")
    return FileResponse(path, headers={"X-Content-Type-Options": "nosniff"})
