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
        if account is not None:
            if version is not None:
                # noinspection PyTypeChecker,PyUnresolvedReferences
                result = list((await self.session.execute(
                    select(AccountState).where(  # type: ignore
                        and_(AccountState.account == account,
                             AccountState.version == version)
                    ).limit(limit + offset)
                )).scalars())
            elif latest_version:
                # noinspection PyTypeChecker,PyUnresolvedReferences
                result = list((await self.session.execute(
                    select(AccountState).where(  # type: ignore
                        and_(AccountState.account == account,
                             AccountState.version == select([func.max(AccountState.version)]).where(
                                 AccountState.account == account))
                    ).limit(limit + offset)
                )).scalars())
            else:
                # noinspection PyTypeChecker,PyUnresolvedReferences
                result = list((await self.session.execute(
                    select(AccountState).where(AccountState.account == account)  # type: ignore
                        .limit(limit + offset)
                )).scalars())
        elif version is not None:
            # noinspection PyTypeChecker,PyUnresolvedReferences
            result = list((await self.session.execute(
                select(AccountState).where(  # type: ignore
                    AccountState.version == version
                ).limit(limit + offset)
            )).scalars())
        elif latest_version:
            # noinspection PyTypeChecker,PyUnresolvedReferences
            subq = (await self.session.execute(
                select([AccountState.account, func.max(AccountState.version)
                       .label('maxversion')])  # type: ignore
                    .group_by(AccountState.account)
            ))
            # noinspection PyTypeChecker,PyUnresolvedReferences
            result = list((await self.session.execute(
                select(AccountState).join(  # type: ignore
                    subq,
                    and_(
                        AccountState.account == subq.account,
                        AccountState.version == subq.maxversion
                    )
                ).limit(limit + offset)
            )).scalars())
        else:
            # noinspection PyTypeChecker,PyUnresolvedReferences
            result = list((await self.session.execute(
                select(AccountState).limit(limit + offset)  # type: ignore
            )).scalars())
        if len(result) < offset:
            raise RpcError(None, 'not found')
        result = result[offset:]
        return [{
            'account': item.account,
            'version': item.version,
            'value': item.value
        } for item in result]
