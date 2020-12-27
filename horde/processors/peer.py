import argparse
import asyncio
import logging
import os
from typing import Any, Optional, Dict, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession  # type: ignore
from sqlalchemy.orm import subqueryload

from horde.models import Blockchain, Transaction, TransactionMutation, AccountState
from horde.processors.node import NodeProcessor
from horde.processors.router import processor, on_requested, on_client_connected, Context, \
    RpcError, on_notified


class BlockchainRejected(Exception):
    pass


@processor
class PeerProcessor(NodeProcessor):
    engine: AsyncEngine
    session: Optional[AsyncSession]
    blockchains: Dict[bytes, Tuple[Any, int]]

    def __init__(self, config: Any, full_config: Any, args: argparse.Namespace):
        super().__init__(config, full_config, args)
        self.engine = create_async_engine('sqlite:///' +
                                          os.path.join(self.config['root'], 'sqlite.db'))
        self.session = None
        self.blockchains = {}

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

    async def save_blockchain(self, blockchain: Any) -> None:
        async with AsyncSession(self.engine) as session:
            async with session.begin():
                session.add(
                    Blockchain(
                        hash=blockchain['hash'], prev_hash=blockchain['prev_hash'],
                        timestamp=blockchain['timestamp'], number=blockchain['number'])
                )
                session.add_all([
                    Transaction(
                        hash=transaction['hash'], signature=transaction['signature'],
                        endorser=transaction['endorser'], timestamp=transaction['timestamp'],
                        blockchain_hash=blockchain['hash'])
                    for transaction in blockchain['transactions']
                ])
                session.add_all([
                    TransactionMutation(
                        hash=mutation['hash'], account=mutation['account'],
                        prev_version=mutation['prev_account_state']['version'],
                        next_version=mutation['next_account_state']['version'],
                        transaction_hash=transaction['hash']
                    )
                    for transaction in blockchain['transactions']
                    for mutation in transaction['mutations']
                ])
                session.add_all([
                    AccountState(
                        hash=account['hash'], version=account['version'],
                        value=account['value'], account=mutation['account']
                    )
                    for transaction in blockchain['transactions']
                    for mutation in transaction['mutations']
                    for account in [mutation['next_account_state']]
                ])

    @on_notified('new-blockchain-verified', peer_type='orderer')
    @on_notified('new-blockchain-verified', peer_type='endorser')
    async def new_blockchain_verified_handler(self, data: Any, context: Context) -> None:
        blockchain_hash = bytes.fromhex(data['hash'])
        if data['verified'] and blockchain_hash in self.blockchains:
            old_tuple = self.blockchains[blockchain_hash]
            if old_tuple[1] + 1 >= self.verify_num:
                del self.blockchains[blockchain_hash]
                await self.save_blockchain(old_tuple[0])
            else:
                new_tuple = old_tuple[0], old_tuple[1] + 1
                self.blockchains[blockchain_hash] = new_tuple

    async def verify_blockchain(self, blockchain: Any) -> None:
        assert self.session is not None
        verified: Optional[bool] = None
        try:
            self.blockchains[blockchain['hash']] = blockchain, 0
            subquery1 = select(func.max(Blockchain.number).label('latest_number')).alias('latest')
            # noinspection PyTypeChecker
            results1 = list((await self.session.execute(
                select(Blockchain)  # type: ignore
                    .join(subquery1, Blockchain.number == subquery1.c.latest_number)
            )).scalars())
            assert len(results1) == 1
            prev: Blockchain = results1[0]
            assert blockchain['number'] == prev.number + 1
            assert blockchain['prev_hash'] == prev.hash
            accounts: Dict[str, Any] = {}
            for transaction in blockchain['transactions']:
                for mutation in transaction['mutations']:
                    account = mutation['account']
                    assert account not in accounts
                    accounts[account] = mutation['prev_account_state']
            subquery2 = select(
                AccountState.account,  # type: ignore
                func.max(AccountState.version).label('latest_version')
            ) \
                .where(AccountState.account.in_(list(accounts.keys()))) \
                .group_by(AccountState.account).alias('latest')
            # noinspection PyUnresolvedReferences,PyTypeChecker
            results2 = list((await self.session.execute(
                select(AccountState).join(  # type: ignore
                    subquery2,
                    and_(
                        AccountState.account == subquery2.c.account,  # type: ignore
                        AccountState.version == subquery2.c.latest_version,  # type: ignore
                    ),
                )
            )).scalars())
            assert len(accounts) == len(results2)
            for account_result in results2:
                account = accounts[account_result.account]
                assert account['version'] == account_result.version
                assert account['value'] == account_result.value
            verified = True
            old_tuple = self.blockchains[blockchain['hash']]
            new_tuple = old_tuple[0], old_tuple[1] + 1
            self.blockchains[blockchain['hash']] = new_tuple
        except:  # pylint:disable=bare-except
            verified = False
        finally:
            assert verified is not None
            await asyncio.gather(*[
                self.notify('new-blockchain-verified', {
                    'hash': blockchain['hash'].hex(),
                    'verified': verified,
                }, connection) for connection in self.connection_to_config])
            logging.info('%s: %s block %d', self.config['id'],
                         'accept' if verified else 'reject', blockchain['number'])

    @on_notified('new-blockchain', peer_type='orderer')
    async def new_blockchain_handler(self, data: Any, context: Context) -> None:
        assert self.session is not None
        blockchain = self.check_valid_blockchain(data)
        await self.verify_blockchain(blockchain)

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
