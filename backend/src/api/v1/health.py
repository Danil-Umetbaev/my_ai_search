from fastapi import APIRouter, Request

health_router = APIRouter(prefix='/health')


@health_router.get('')
async def health_check(request: Request):
    models = getattr(request.app.state, 'models', {})
    return {'status': 'ok', 'models': models.get('status', 'loading'), 'stage': models.get('stage')}
