import asyncio
from functools import partial

from starlette.responses import JSONResponse


_model_lock = asyncio.Lock()
_support_jobs = set()


async def run_support_model(function, *args, timeout=45):
    if len(_support_jobs) >= 16:
        raise RuntimeError("Support model queue is full")
    task = asyncio.create_task(run_model(function, *args))
    _support_jobs.add(task)

    def finish(done):
        _support_jobs.discard(done)
        if not done.cancelled():
            done.exception()

    task.add_done_callback(finish)
    return await asyncio.wait_for(asyncio.shield(task), timeout=timeout)


async def run_model(function, *args, **kwargs):
    async with _model_lock:
        future = asyncio.get_running_loop().run_in_executor(
            None, partial(function, *args, **kwargs),
        )
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            await asyncio.shield(future)
            raise


class AICapacityMiddleware:
    """Bound accepted requests; model calls queue separately in one worker."""

    def __init__(self, app):
        self.app = app
        self.max_requests = 16
        self.tasks = set()

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '').rstrip('/')
        model_request = path == '/api/v1/chat/messages' or (
            path.startswith('/api/v1/support/sessions/') and path.endswith('/messages')
        )
        if (scope['type'] != 'http' or scope.get('method') != 'POST'
                or not model_request):
            return await self.app(scope, receive, send)
        if len(self.tasks) >= self.max_requests:
            return await JSONResponse(
                {'code': 'AI_SERVICE_BUSY', 'message': 'Очередь запросов заполнена. Попробуйте позже.'},
                status_code=429, headers={'Retry-After': '10'},
            )(scope, receive, send)

        task = asyncio.create_task(self.app(scope, receive, send))
        self.tasks.add(task)

        def complete(done):
            self.tasks.discard(done)
            if not done.cancelled():
                done.exception()
        task.add_done_callback(complete)
        await asyncio.shield(task)
