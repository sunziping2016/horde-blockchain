from typing import Any

from horde.processors.router import Router, Context, processor, on_requested, on_client_connected


@processor
class OrdererProcessor(Router):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_listen = True

    @on_client_connected()
    async def on_client_connected(self, context: Context) -> None:
        if context.is_peer_unknown():
            context.change_peer_id(await context.request('who-are-you'))
        print(context.peer_config())
        # await context.notify('shutdown-server')

    @on_requested('ping')
    async def ping_handler(self, data: Any, context: Context) -> Any:
        await context.notify('message', 'you are %s' % context.peer_id)
        return data
