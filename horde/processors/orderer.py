import asyncio
from typing import Any

from horde.processors.peer import PeerProcessor
from horde.processors.router import Context, processor, on_requested, \
    on_client_connected


@processor
class OrdererProcessor(PeerProcessor):

    async def start(self) -> None:
        host, port = self.config['bind_addr']
        server_id = await self.start_server(host, port)

        async def close():
            await asyncio.sleep(2)
            self.close_server(server_id)
        await self.task_queue.put(asyncio.create_task(close()))
        await super().start()

    @on_client_connected()
    async def on_client_connected(self, context: Context) -> None:
        if context.peer_config() is None:
            peer_id = await context.request('who-are-you')
            context.set_peer_config(self.configs[peer_id])

    @on_requested('ping')
    async def ping_handler(self, data: Any, context: Context) -> Any:
        print('ping %s' % context.connection_id)
        return data
