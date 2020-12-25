import asyncio
from typing import Any

from horde.processors.router import Router, Context, processor, on_requested, \
    on_client_connected, RpcError


@processor
class OrdererProcessor(Router):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_listen = True

    @on_client_connected()
    async def on_client_connected(self, context: Context) -> None:
        if context.is_peer_unknown():
            peer_id = await context.request('who-are-you')
            print(peer_id)
            context.change_peer_id(peer_id)
        await asyncio.sleep(0.5)
        await context.notify('shutdown')
        context.close_connection()
        self.close_server()

    @on_requested('ping')
    async def ping_handler(self, data: Any, context: Context) -> Any:
        await context.notify('message', 'you are %s' % context.peer_id)
        if data == 'world':
            raise RpcError('I don\'t like world')
        return data
