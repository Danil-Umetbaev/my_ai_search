import asyncio

from starlette.responses import JSONResponse


class AICapacityMiddleware:
    """One in-flight chat request per process, including model initialization.

    Deploy with one uvicorn worker. Retain the slot until work finishes even
    if the HTTP task is cancelled: to_thread inference cannot be cancelled.
    """

    def __init__(self, app):
        self.app = app
        self.busy = False
        self.tasks = set()

    async def __call__(self, scope, receive, send):
        if (scope['type'] != 'http' or scope.get('method') != 'POST'
                or scope.get('path', '').rstrip('/') != '/api/v1/chat/messages'):
            return await self.app(scope, receive, send)
        if self.busy:
            return await JSONResponse(
                {'code': 'AI_SERVICE_BUSY', 'message': 'Сервис занят. Попробуйте позже.'},
                status_code=429, headers={'Retry-After': '10'},
            )(scope, receive, send)

        self.busy = True
        task = asyncio.create_task(self.app(scope, receive, send))
        self.tasks.add(task)

        def complete(done):
            self.busy = False
            self.tasks.discard(done)
            if not done.cancelled():
                done.exception()  # Retrieve exceptions even after HTTP cancellation.

        task.add_done_callback(complete)
        await asyncio.shield(task)
