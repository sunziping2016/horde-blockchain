import argparse
import asyncio
import logging
from datetime import datetime
from typing import Any, List, Set

from sqlalchemy import select, func

from horde.models import Blockchain
from horde.processors.node import WrongHash, WrongSignature
from horde.processors.peer import PeerProcessor
from horde.processors.router import processor, Context, on_requested, RpcError


@processor
class OrdererProcessor(PeerProcessor):
    transactions: List[Any]
    mutated_accounts: Set[str]
    max_transaction_pool: int
    blockchain_creation_timout: float
    new_blockchain_signal: asyncio.Queue  # item is None: used as trigger

    def __init__(self, config: Any, full_config: Any, args: argparse.Namespace):
        super().__init__(config, full_config, args)
        self.transactions = []
        self.mutated_accounts = set()
        self.max_transaction_pool = 10
        self.blockchain_creation_timout = 1.0
        self.new_blockchain_signal = asyncio.Queue()

    async def generate_blockchain(self, transactions: List[Any],
                                  mutated_accounts: Set[str]) -> None:
        logging.info('%s: generate block started', self.config['id'])
        assert self.session is not None
        subquery = select(func.max(Blockchain.number).label('latest_number')).alias('latest')
        # noinspection PyTypeChecker
        result = list((await self.session.execute(
            select(Blockchain)  # type: ignore
                .join(subquery, Blockchain.number == subquery.c.latest_number)
        )).scalars())
        assert len(result) == 1
        prev: Blockchain = result[0]
        timestamp = datetime.utcnow()
        number = prev.number + 1
        blockchain_hash = Blockchain.compute_hash(
            prev.hash, timestamp, number,
            [transaction['hash'] for transaction in transactions])
        blockchain = {
            'hash': blockchain_hash,
            'prev_hash': prev.hash,
            'timestamp': timestamp,
            'number': number,
            'transactions': transactions
        }
        # await self.save_blockchain(blockchain)
        await asyncio.gather(*[
            self.notify('new-blockchain', self.serialize_blockchain(blockchain),
                        connection)
            for connection in self.connection_to_config])
        logging.info('%s: generate block finished %d', self.config['id'], number)

    @on_requested('submit-transactions', peer_type='admin')
    @on_requested('submit-transactions', peer_type='client')
    async def submit_transaction(self, data: Any, context: Context) -> Any:
        try:
            assert isinstance(data, list)
            transactions = [self.check_valid_transaction(item) for item in data]
        except (KeyError, AssertionError, ValueError) as error:
            raise RpcError(None, 'bad request') from error
        except WrongHash as error:
            raise RpcError(None, 'wrong hash') from error
        except WrongSignature as error:
            raise RpcError(None, 'wrong signature') from error
        accounts = set()
        for transaction in transactions:
            for mutation in transaction['mutations']:
                account = mutation['account']
                if account in accounts or account in self.mutated_accounts:
                    raise RpcError(None, 'conflict transaction')
                accounts.add(account)
        self.transactions += transactions
        self.mutated_accounts |= accounts
        await self.new_blockchain_signal.put(None)

    async def start(self) -> None:
        async def create_blockchain_loop():
            try:
                while True:
                    new_blockchain_signal_task = asyncio.create_task(
                        self.new_blockchain_signal.get())
                    timeout = False
                    try:
                        await asyncio.wait_for(new_blockchain_signal_task,
                                               timeout=self.blockchain_creation_timout)
                    except asyncio.TimeoutError:
                        timeout = True
                    if self.transactions and \
                            (timeout or len(self.transactions) >= self.max_transaction_pool):
                        transactions = self.transactions  # swap out to avoid data race
                        mutated_accounts = self.mutated_accounts
                        self.transactions = []
                        self.mutated_accounts = set()
                        await self.generate_blockchain(transactions, mutated_accounts)
            except asyncio.CancelledError:
                pass
        create_blockchain_loop_task = asyncio.create_task(create_blockchain_loop())
        await super().start()
        create_blockchain_loop_task.cancel()
