from typing import Any

from horde.processors.router import Router, Context, processor, on_requested, on_client_connected


@processor
class OrdererProcessor(Router):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_listen = True

    @on_client_connected()
    async def on_client_connected(self, context: Context) -> None:
        print('%s accepted %s' % (self.config['id'], context.peer_id))

    @on_requested('ping')
    async def ping_handler(self, data: Any, context: Context) -> Any:
        await context.notify('message', 'it\'s a test')
        return data
