import argparse
import os
from typing import Any, Optional

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession  # type: ignore
from sqlalchemy.orm import subqueryload

from horde.models import Blockchain, Transaction, TransactionMutation, AccountState
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
        assert self.session is not None
        try:
            blockchain_number = data['blockchain_number']
            assert isinstance(blockchain_number, int)
        except (AssertionError, TypeError, KeyError) as error:
            raise RpcError(None, 'bad request') from error
        # noinspection PyTypeChecker,PyUnresolvedReferences
        result = list((await self.session.execute(
            select(Blockchain).options(  # type: ignore
                subqueryload(Blockchain.transactions)
                    .subqueryload(Transaction.mutations)
                    .options(
                        subqueryload(TransactionMutation.prev_account_state),
                        subqueryload(TransactionMutation.next_account_state)))
                    .where(Blockchain.number == blockchain_number)
            )).scalars())
        if len(result) == 0:
            raise RpcError(None, 'not found')
        item: Blockchain = result[0]
        return item.serialize()

    @on_requested('query-accounts', peer_type='admin')
    @on_requested('query-accounts', peer_type='client')
    async def query_accounts_handler(self, data: Any, context: Context) -> Any:
        assert self.session is not None
        try:
            account = None
            if 'account' in data:
                account = data['account']
                assert isinstance(account, str)
            version = None
            if 'version' in data:
                version = data['version']
                assert isinstance(version, int)
            latest_version = None
            if version is None and 'latest_version' in data:
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
            subquery = select(
                AccountState.account,  # type: ignore
                func.max(AccountState.version).label('latest_version')
            )
            if condition is not None:
                subquery = subquery.where(condition)
            subquery = subquery.group_by(AccountState.account).alias('latest')  # type: ignore
            # noinspection PyUnresolvedReferences,PyTypeChecker
            stmt = select(AccountState).join(subquery, and_(  # type: ignore
                AccountState.account == subquery.c.account,  # type: ignore
                AccountState.version == subquery.c.latest_version,  # type: ignore
            ))
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
        assert self.session is not None
        try:
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
                .limit(limit)
                .offset(offset)
        )).scalars())
        # noinspection PyTypeChecker
        return [{
            'hash': item.hash.hex(),
            'number': item.number
        } for item in result]
