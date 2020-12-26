from json import JSONDecodeError

from aiohttp import web

from horde.processors.client import ClientProcessor
from horde.processors.router import processor, RpcError


@processor
class AdminProcessor(ClientProcessor):

    def generate_routes(self):
        self.app.add_routes([
            web.post(r'/api/transaction/make-money', self.make_money_api),
        ])
        super().generate_routes()

    async def make_money_api(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            endorser = data['endorser']
            assert isinstance(endorser, str)
            amount = data['amount']
            assert isinstance(amount, float)
        except (JSONDecodeError, KeyError, ValueError):
            return web.json_response({
                'error': {
                    'message': 'invalid query',
                },
            }, status=400)
        connection = self.find_peer(endorser)
        if connection is None:
            return web.json_response({'error': {'message': 'endorser offline'}}, status=400)
        try:
            result = await self.request('make-money', {'amount': amount}, connection)
            return web.json_response({'result': result})
        except RpcError as error:
            return web.json_response({
                'error': {
                    'message': str(error),
                    'data': error.data,
                },
            }, status=400)
