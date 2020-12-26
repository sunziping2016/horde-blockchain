import argparse
import os
from typing import Any, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession  # type: ignore
from sqlalchemy.orm import subqueryload

from horde.models import Blockchain, Transaction, AccountState
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

    @on_requested('query-accounts', peer_type='admin')
    @on_requested('query-accounts', peer_type='client')
    async def query_accounts_handler(self, data: Any, context: Context) -> Any:
        try:
            assert self.session is not None
            account = None
            if 'account' in data:
                account = data['account']
                assert isinstance(account, str)
            version = None
            if 'version' in data:
                version = data['version']
                assert isinstance(version, int)
            latest_version = None
            if version is not None and 'latest_version' in data:
                latest_version = data['latest_version']
                assert isinstance(latest_version, bool)
            limit = 15
            if 'limit' in data:
                limit = data['limit']
                assert isinstance(limit, int)
                assert limit >= 0
            offset = 0
            if 'offset' in data:
                offset = data['offset']
                assert isinstance(offset, int)
                assert offset >= 0
        except (AssertionError, TypeError, KeyError) as error:
            raise RpcError(None, 'bad request') from error
        condition: Any = None
        if account is not None and version is not None:
            condition = and_(AccountState.account == account, AccountState.version == version)
        elif account is not None:
            condition = AccountState.account == account
        elif version is not None:
            condition = AccountState.version == version
        if version is None and latest_version:
            subquery = select(AccountState.account, func.max(AccountState.version))  # type: ignore
            if condition is not None:
                subquery = subquery.where(condition)
            subquery = subquery.group_by(AccountState.account)
            # noinspection PyUnresolvedReferences,PyTypeChecker
            stmt = select(AccountState).join(  # type: ignore
                subquery,
                and_(
                    AccountState.account == subquery.account,  # type: ignore
                    AccountState.version == subquery.version,  # type: ignore
                ),
            )
        else:
            # noinspection PyTypeChecker
            stmt = select(AccountState)  # type: ignore
            if condition is not None:
                stmt = stmt.where(condition)  # type: ignore
        stmt = stmt.offset(offset).limit(limit)  # type: ignore
        result = list((await self.session.execute(stmt)).scalars())
        return [{
            'account': item.account,
            'version': item.version,
            'value': float(item.value),
        } for item in result]

    @on_requested('list-blockchains', peer_type='admin')
    @on_requested('list-blockchains', peer_type='client')
    async def list_blockchains_handler(self, data: Any, context: Context) -> Any:
        try:
            assert self.session is not None
            asc = False
            if 'asc' in data:
                asc = data['asc']
                assert isinstance(asc, bool)
            limit = 15
            if 'limit' in data:
                limit = data['limit']
                assert isinstance(limit, int)
                assert limit >= 0
            offset = 0
            if 'offset' in data:
                offset = data['offset']
                assert isinstance(offset, int)
                assert offset >= 0
        except (AssertionError, TypeError, KeyError) as error:
            raise RpcError(None, 'bad request') from error
        # noinspection PyTypeChecker,PyUnresolvedReferences
        result = list((await self.session.execute(
            select(Blockchain)  # type: ignore
            .order_by(Blockchain.number if asc else Blockchain.number.desc())
                .limit(limit + offset)
        )).scalars())
        if len(result) < offset:
            raise RpcError(None, 'not found')
        # noinspection PyTypeChecker
        return [{
            'hash': item.hash,
            'number': item.number
        } for item in result[offset:]]
