from horde.processors.peer import PeerProcessor
from horde.processors.router import processor


@processor
class EndorserProcessor(PeerProcessor):

    async def start(self) -> None:
        for peer in self.full_config['peers']:
            if peer['id'] == self.config['id']:
                break
            peer_host, peer_port = peer['public_addr']
            await self.start_connection(peer_host, peer_port, self.configs[peer['id']])
        await super().start()
