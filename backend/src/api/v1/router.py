from fastapi import APIRouter
from src.api.v1.example import router as example_router
router = APIRouter(prefix='/api/v1')

router.include_router(example_router)

