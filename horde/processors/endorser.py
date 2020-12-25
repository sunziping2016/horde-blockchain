import asyncio
from typing import Any

from horde.processors.router import Router, processor, on_server_connected, Context, on_notified


@processor
class EndorserProcessor(Router):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_listen = True

    @on_server_connected()
    async def on_server_connected(self, context: Context) -> None:
        print('%s connected to %s' % (self.config['id'], context.peer_id))
        reply1, reply2 = await asyncio.gather(
            context.request('ping', 'hello'),
            context.request('ping', 'world'),
        )
        print('%s: replies: %s %s' % (self.config['id'], reply1, reply2))

    @on_notified('message')
    async def on_message_notified(self, data: Any, context: Context) -> None:
        print('%s: message: %s' % (self.config['id'], data))
