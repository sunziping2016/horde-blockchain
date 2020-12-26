import argparse
import asyncio
from typing import Any, List

from horde.processors.peer import PeerProcessor
from horde.processors.router import processor, Context, on_requested


@processor
class OrdererProcessor(PeerProcessor):
    transactions: List[Any]
    max_transaction_pool: int
    blockchain_creation_timout: float
    new_blockchain_signal: asyncio.Queue  # item is None: used as trigger

    def __init__(self, config: Any, full_config: Any, args: argparse.Namespace):
        super().__init__(config, full_config, args)
        self.transactions = []
        self.max_transaction_pool = 10
        self.blockchain_creation_timout = 5.0
        self.new_blockchain_signal = asyncio.Queue()

    async def generate_blockchain(self, transactions: List[Any]) -> None:
        # TODO: generate blockchain #8
        # TODO: PBFT(Practical Byzantine Fault Tolerance) #9
        pass

    @on_requested('submit', peer_type='admin')
    @on_requested('submit', peer_type='client')
    async def submit(self, data: Any, context: Context) -> Any:
        # TODO: validate signature #8 and detect conflicts
        self.transactions.append(data)
        await self.new_blockchain_signal.put(None)
        return {
            'ok': True,
        }

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
                        self.transactions = []
                        await self.generate_blockchain(transactions)
            except asyncio.CancelledError:
                pass
        create_blockchain_loop_task = asyncio.create_task(create_blockchain_loop())
        await super().start()
        create_blockchain_loop_task.cancel()
