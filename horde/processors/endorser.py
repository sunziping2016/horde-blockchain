import asyncio

from horde.processors.router import Router, processor, on_server_connected, Context


@processor
class EndorserProcessor(Router):

    async def start(self) -> None:
        peer_host, peer_port = self.configs['orderer']['public_addr']
        await self.start_connection(peer_host, peer_port, self.configs['orderer'])
        await super().start()

    @on_server_connected('orderer')
    async def on_server_connected(self, context: Context) -> None:
        # How to start two request at one time
        reply1, reply2 = await asyncio.gather(
            context.request('ping', 'hello'),
            context.request('ping', 'world')
        )
        print('%s: replies: %s %s' % (self.config['id'], reply1, reply2))
        # Not necessary, this is how to sleep in async way
        await asyncio.sleep(0.2)
        await context.notify('shutdown')
