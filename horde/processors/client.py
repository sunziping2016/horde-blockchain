import argparse
import asyncio
import json
import logging
import os
import webbrowser
from json import JSONDecodeError
from typing import Any, Optional, Tuple

import aiohttp
from aiohttp import web

from horde.processors.node import NodeProcessor
from horde.processors.router import processor, RpcError, on_notified, Context


@processor
class ClientProcessor(NodeProcessor):
    app: web.Application
    websocket_outgoing_queue: asyncio.Queue

    def __init__(self, config: Any, full_config: Any, args: argparse.Namespace):
        super().__init__(config, full_config, args)
        self.app = web.Application()
        self.websocket_outgoing_queue = asyncio.Queue()
        self.generate_routes()

    def generate_routes(self):
        web_root_path = os.path.join(self.full_config['web']['static_root'])
        os.makedirs(web_root_path, exist_ok=True)
        self.app.add_routes([
            web.get(r'/api/ws', self.websocket_handler),
            web.post(r'/api/transaction/transfer-money', self.transfer_money_api),
            web.post(r'/api/transaction/submit', self.submit_transactions_api),
            web.get(r'/api/connections', self.global_topology_api),
            web.get(r'/api/{peer}/connections', self.query_topology_api),
            web.get(r'/api/{peer}/accounts', self.query_accounts_api),
            web.get(r'/api/{peer}/blockchains/', self.list_blockchains_api),
            web.get(r'/api/{peer}/blockchains/{blockchain:\d+}', self.query_blockchain_api),
            web.static(r'/', os.path.join(web_root_path)),
        ])

    async def websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        socket = web.WebSocketResponse()
        await socket.prepare(request)

        async def retrieve_websocket():
            try:
                return await socket.__anext__(), None
            except StopAsyncIteration as err:
                return None, err
        outgoing_task = asyncio.create_task(self.websocket_outgoing_queue.get())
        incoming_task = asyncio.create_task(retrieve_websocket())
        while True:
            done, _ = await asyncio.wait({outgoing_task, incoming_task},
                                         return_when=asyncio.FIRST_COMPLETED)
            if incoming_task in done:
                result: Tuple[Optional[aiohttp.WSMessage], Optional[Exception]] = \
                    await incoming_task
                if result[1] is not None:
                    break
                msg = result[0]
                assert msg is not None
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'close':
                        await socket.close()
                        break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logging.debug('%s: ws connection closed with exception %s',
                                  self.config['id'], socket.exception())
                incoming_task = asyncio.create_task(retrieve_websocket())
            if outgoing_task in done:
                data = await outgoing_task
                await socket.send_str(json.dumps(data))
                outgoing_task = asyncio.create_task(self.websocket_outgoing_queue.get())
        logging.debug('%s: websocket connection closed', self.config['id'])
        return socket

    @on_notified('new-blockchain', peer_type='orderer')
    async def new_blockchain_handler(self, data: Any, context: Context) -> None:
        await self.websocket_outgoing_queue.put({
            'type': 'new-blockchain',
            'data': data,
        })

    @on_notified('new-blockchain-verified', peer_type='orderer')
    @on_notified('new-blockchain-verified', peer_type='endorser')
    async def new_blockchain_verified_handler(self, data: Any, context: Context) -> None:
        await self.websocket_outgoing_queue.put({
            'type': 'new-blockchain-verified',
            'data': data,
        })

    async def start(self) -> None:
        host = '127.0.0.1'
        port = self.config['port']
        # pylint:disable=protected-access
        await self.task_queue.put(asyncio.create_task(web._run_app(
            self.app, host=host, port=port)))
        if self.args.open:
            async def open_webpage(url):
                await asyncio.sleep(0.2)
                webbrowser.open(url)
            await self.task_queue.put(asyncio.create_task(open_webpage(
                'http://%s:%d/index.html' % (host, port))))
        for peer in self.full_config['peers']:
            peer_host, peer_port = peer['public_addr']
            await self.start_connection(peer_host, peer_port, self.configs[peer['id']])
        await super().start()

    def find_peer(self, id_) -> Optional[str]:
        connection: Optional[str] = None
        for connection2, config in self.connection_to_config.items():
            if config is not None and config['id'] == id_:
                connection = connection2
                break
        return connection

    async def global_topology_api(self, request: web.Request) -> web.Response:
        connections = []
        ids = []
        for connection, config in self.connection_to_config.items():
            if config is not None:
                connections.append(connection)
                ids.append(config['id'])
        requests = []
        for connection in connections:
            new_request = self.request('query-topology', None, connection)
            requests.append(new_request)
        try:
            results = await asyncio.gather(*requests)
            return web.json_response({
                ids[index]: result for index, result in enumerate(results)
            })
        except RpcError as error:
            return web.json_response({
                'error': {
                    'message': str(error),
                    'data': error.data,
                },
            }, status=400)

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
        connection = self.find_peer(peer)
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
        connection = self.find_peer(peer)
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

    async def query_accounts_api(self, request: web.Request) -> web.Response:
        try:
            peer = request.match_info.get('peer')
            assert peer is not None
            account = request.rel_url.query.get('account')
            raw_version = request.rel_url.query.get('version')
            version = int(raw_version) if raw_version is not None else None
            raw_latest_version = request.rel_url.query.get('latest-version')
            if raw_latest_version is not None:
                assert raw_latest_version in ['true', 'false']
                latest_version: Optional[bool] = raw_latest_version == 'true'
            else:
                latest_version = None
            raw_limit = request.rel_url.query.get('limit')
            limit = int(raw_limit) if raw_limit is not None else None
            raw_offset = request.rel_url.query.get('offset')
            offset = int(raw_offset) if raw_offset is not None else None
        except (ValueError, AssertionError):
            return web.json_response({
                'error': {
                    'message': 'invalid query parameter',
                },
            }, status=400)
        connection = self.find_peer(peer)
        if connection is None:
            return web.json_response({
                'error': {
                    'message': 'peer offline',
                },
            }, status=400)
        query: Any = {}
        if account is not None:
            query['account'] = account
        if version is not None:
            query['version'] = version
        if latest_version is not None:
            query['latest_version'] = latest_version
        if limit is not None:
            query['limit'] = limit
        if offset is not None:
            query['offset'] = offset
        try:
            result = await self.request('query-accounts', query, connection)
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

    async def list_blockchains_api(self, request: web.Request) -> web.Response:
        try:
            raw_asc = request.rel_url.query.get('asc')
            if raw_asc is not None:
                assert raw_asc in ['true', 'false']
                asc: Optional[bool] = raw_asc == 'true'
            else:
                asc = None
            peer = request.match_info.get('peer')
            raw_limit = request.rel_url.query.get('limit')
            limit = int(raw_limit) if raw_limit is not None else None
            raw_offset = request.rel_url.query.get('offset')
            offset = int(raw_offset) if raw_offset is not None else None
        except (ValueError, AssertionError):
            return web.json_response({
                'error': {
                    'message': 'invalid query parameter',
                },
            }, status=400)
        connection = self.find_peer(peer)
        if connection is None:
            return web.json_response({
                'error': {
                    'message': 'peer offline',
                },
            }, status=400)
        query: Any = {}
        if asc is not None:
            query['asc'] = asc
        if limit is not None:
            query['limit'] = limit
        if offset is not None:
            query['offset'] = offset
        try:
            result = await self.request('list-blockchains', query, connection)
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

    async def transfer_money_api(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            endorser = body['endorser']
            assert isinstance(endorser, str)
            data = body['data']
        except (JSONDecodeError, KeyError, AssertionError, TypeError):
            return web.json_response({'error': {'message': 'invalid query'}}, status=400)
        connection = self.find_peer(endorser)
        if connection is None:
            return web.json_response({'error': {'message': 'endorser offline'}}, status=400)
        try:
            result = await self.request('transfer-money', data, connection)
            return web.json_response({'result': result})
        except RpcError as error:
            return web.json_response({
                'error': {
                    'message': str(error),
                    'data': error.data,
                },
            }, status=400)

    async def submit_transactions_api(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            orderer = body['orderer']
            assert isinstance(orderer, str)
            data = body['data']
        except (JSONDecodeError, KeyError, AssertionError, TypeError):
            return web.json_response({'error': {'message': 'invalid query'}}, status=400)
        connection = self.find_peer(orderer)
        if connection is None:
            return web.json_response({'error': {'message': 'orderer offline'}}, status=400)
        try:
            result = await self.request('submit-transactions', data, connection)
            return web.json_response({'result': result})
        except RpcError as error:
            return web.json_response({
                'error': {
                    'message': str(error),
                    'data': error.data,
                },
            }, status=400)
