import asyncio
from typing import Any

from horde.processors.peer import PeerProcessor
from horde.processors.router import processor, on_server_connected, Context, on_requested


@processor
class EndorserProcessor(PeerProcessor):

    async def start(self) -> None:
        peer_host, peer_port = self.configs['orderer']['public_addr']
        await self.start_connection(peer_host, peer_port, self.configs['orderer'])
        await super().start()

    @on_requested('who-are-you')
    async def who_are_you_handler(self, data: Any, context: Context) -> Any:
        return self.config['id']

    @on_server_connected('orderer')
    async def on_server_connected(self, context: Context) -> None:
        await asyncio.sleep(1)
        await context.request('ping', 'hello')
