import asyncio
from typing import Any

from horde.processors.router import Router, processor, on_server_connected, Context, \
    on_notified, on_requested


@processor
class EndorserProcessor(Router):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_listen = True

    @on_server_connected()
    async def on_server_connected(self, context: Context) -> None:
        await asyncio.sleep(0.2)
        reply1, reply2 = await asyncio.gather(
            context.request('ping', 'hello'),
            context.request('ping', 'world'),
        )
        print('%s: replies: %s %s' % (self.config['id'], reply1, reply2))

    @on_requested('who-are-you')
    async def who_are_you_requested(self, data: Any, context: Context) -> str:
        return self.config['id']

    @on_notified('message')
    async def on_message_notified(self, data: Any, context: Context) -> None:
        print('%s: message: %s' % (self.config['id'], data))

    @on_notified('shutdown')
    async def shutdown_handler(self, data: Any, context: Context) -> Any:
        context.close_connection()
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
