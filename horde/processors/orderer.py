import asyncio
from typing import Any

from horde.processors.router import Router, Context, processor, on_requested, \
    on_client_connected, on_notified, RpcError


@processor
class OrdererProcessor(Router):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_listen = True

    @on_client_connected()
    async def on_client_connected(self, context: Context) -> None:
        if context.is_peer_unknown():
            context.change_peer_id(await context.request('who-are-you'))
        await asyncio.sleep(0.4)
        await context.notify('shutdown')

    @on_requested('ping')
    async def ping_handler(self, data: Any, context: Context) -> Any:
        await context.notify('message', 'you are %s' % context.peer_id)
        if data == 'world':
            raise RpcError('I don\'t like world')
        return data

    @on_notified('shutdown')
    async def shutdown_handler(self, data: Any, context: Context) -> Any:
        context.close_connection()
        self.close_server()
