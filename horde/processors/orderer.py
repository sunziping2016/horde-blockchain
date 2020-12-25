import logging
from typing import Any

from horde.processors.router import Router, Context, processor, on_requested, on_notified


@processor
class OrdererProcessor(Router):

    async def start(self) -> None:
        host, port = self.config['bind_addr']
        await self.start_server(host, port)
        await super().start()

    @on_requested('ping')
    async def ping_handler(self, data: Any, context: Context) -> Any:
        logging.info('%s: pinged with data: %s', self.config['id'], data)
        return data

    @on_notified('shutdown')
    async def shutdown_handler(self, data: Any, context: Context) -> Any:
        logging.info('%s: shutdown server', self.config['id'])
        context.close_server()
