import argparse
import os
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession  # type: ignore
from sqlalchemy.orm import subqueryload

from horde.models import Blockchain, Transaction
from horde.processors.node import NodeProcessor
from horde.processors.router import processor, on_requested, on_client_connected, Context, RpcError


@processor
class PeerProcessor(NodeProcessor):
    engine: AsyncEngine
    session: Optional[AsyncSession]

    def __init__(self, config: Any, full_config: Any, args: argparse.Namespace):
        super().__init__(config, full_config, args)
        self.engine = create_async_engine('sqlite:///' +
                                          os.path.join(self.config['root'], 'sqlite.db'))
        self.session = None

    @on_client_connected()
    async def on_client_connected(self, context: Context) -> None:
        if context.peer_config() is None:
            peer_id = await context.request('who-are-you')
            context.set_peer_config(self.configs[peer_id])

    async def start(self) -> None:
        host, port = self.config['bind_addr']
        await self.start_server(host, port)
        self.session = AsyncSession(self.engine)
        await super().start()
        await self.session.close()
        self.session = None

    @on_requested('query-blockchain', peer_type='admin')
    @on_requested('query-blockchain', peer_type='client')
    async def query_blockchain_handler(self, data: Any, context: Context) -> Any:
        try:
            assert self.session is not None
            blockchain_number = data['blockchain_number']
            assert isinstance(blockchain_number, int)
        except (AssertionError, TypeError, KeyError) as error:
            raise RpcError(None, 'bad request') from error
        # noinspection PyTypeChecker,PyUnresolvedReferences
        result = list((await self.session.execute(
            select(Blockchain)  # type: ignore
                .options(subqueryload(Blockchain.transactions)
                         .subqueryload(Transaction.mutations))
                .where(Blockchain.number == blockchain_number)
        )).scalars())
        if len(result) == 0:
            raise RpcError(None, 'not found')
        item: Blockchain = result[0]
        # noinspection PyTypeChecker
        return {
            'hash': item.hash.hex(),
            'prev_hash': item.prev_hash.hex(),
            'timestamp': item.timestamp.isoformat(),
            'number': item.number,
            'transactions': [{
                'hash': transaction.hash.hex(),
                'endorser': transaction.endorser,
                'signature': transaction.signature.hex(),
                'mutations': [{
                    'hash': mutation.hash.hex(),
                    'account': mutation.account,
                    'prev_version': mutation.prev_version,
                    'next_version': mutation.next_version,
                } for mutation in transaction.mutations]
            } for transaction in item.transactions]  # type: ignore
        }

    @on_requested('query-topology', peer_type='admin')
    @on_requested('query-topology', peer_type='client')
    async def query_topology_handler(self, data: Any, context: Context) -> Any:
        # assert self.session is not None
        connections = set()
        if None in self.server_to_connections:
            connections = self.server_to_connections[None]
        result = []
        for connection in connections:
            config = self.connection_to_config[connection]
            if config is not None:
                result.append(config['id'])
        return result
