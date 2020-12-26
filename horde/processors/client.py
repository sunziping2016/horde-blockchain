import argparse
import asyncio
import os
import webbrowser
from typing import Any, Optional

from aiohttp import web

from horde.processors.node import NodeProcessor
from horde.processors.router import processor, RpcError


@processor
class ClientProcessor(NodeProcessor):
    app: web.Application

    def __init__(self, config: Any, full_config: Any, args: argparse.Namespace):
        super().__init__(config, full_config, args)
        self.app = web.Application()
        self.generate_routes()

    def generate_routes(self):
        self.app.router.add_get('/api/{peer}/blockchains/{blockchain}', self.query_blockchain_api)
        self.app.router.add_get('/api/{peer}/connections', self.query_topology_api)
        self.app.router.add_static('/', os.path.join(self.full_config['web']['static_root']))

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
        for peer in self.full_config['peers']:
            peer_host, peer_port = peer['public_addr']
            await self.start_connection(peer_host, peer_port, self.configs[peer['id']])
        await super().start()

    async def query_blockchain_api(self, request: web.Request) -> web.Response:
        peer = request.match_info.get('peer')
        assert peer is not None
        try:
            raw_blockchain = request.match_info.get('blockchain')
            assert raw_blockchain is not None
            blockchain = int(raw_blockchain)
        except ValueError:
            return web.json_response({
                'error': {
                    'message': 'invalid blockchain number',
                },
            }, status=400)
        connection: Optional[str] = None
        for connection2, config in self.connection_to_config.items():
            if config is not None and config['id'] == peer:
                connection = connection2
                break
        if connection is None:
            return web.json_response({
                'error': {
                    'message': 'peer offline',
                },
            }, status=400)
        try:
            result = await self.request('query-blockchain', {
                'blockchain_number': blockchain,
            }, connection)
            return web.json_response({
                'result': result,
            })
        except RpcError as error:
            return web.json_response({
                'error': {
                    'message': str(error),
                    'data': error.data,
                },
            }, status=400)

    async def query_topology_api(self, request: web.Request) -> web.Response:
        peer = request.match_info.get('peer')
        assert peer is not None
        connection: Optional[str] = None
        for connection2, config in self.connection_to_config.items():
            if config is not None and config['id'] == peer:
                connection = connection2
                break
        if connection is None:
            return web.json_response({
                'error': {
                    'message': 'peer offline',
                },
            }, status=400)
        try:
            result = await self.request('query-topology', None, connection)
            return web.json_response({
                'result': result,
            })
        except RpcError as error:
            return web.json_response({
                'error': {
                    'message': str(error),
                    'data': error.data,
                },
            }, status=400)
