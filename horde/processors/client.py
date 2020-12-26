import argparse
import asyncio
import os
import webbrowser
from typing import Any

from aiohttp import web

from horde.processors.node import NodeProcessor
from horde.processors.router import processor


@processor
class ClientProcessor(NodeProcessor):
    app: web.Application

    def __init__(self, config: Any, full_config: Any, args: argparse.Namespace):
        super().__init__(config, full_config, args)
        self.app = web.Application()
        self.app.router.add_static('/', os.path.join(full_config['web']['static_root']))

    async def start(self) -> None:
        # pylint:disable=protected-access
        await self.task_queue.put(asyncio.create_task(web._run_app(
            self.app,
            host=self.full_config['web']['bind_addr'][0],
            port=self.full_config['web']['bind_addr'][1]
        )))
        if self.args.open:
            async def open_webpage(url):
                await asyncio.sleep(0.2)
                webbrowser.open(url)
            await self.task_queue.put(asyncio.create_task(open_webpage(
                'http://%s:%d/index.html' % tuple(self.full_config['web']['public_addr']))))
        await super().start()
