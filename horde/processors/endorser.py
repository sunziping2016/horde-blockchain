from datetime import datetime
from typing import Any, Tuple, Dict, List

from sqlalchemy import select, func, or_, and_

from horde.models import AccountState, ACCOUNT_PRECISION, TransactionMutation, Transaction
from horde.processors.peer import PeerProcessor
from horde.processors.router import processor, on_requested, Context, RpcError


@processor
class EndorserProcessor(PeerProcessor):

    async def start(self) -> None:
        for peer in self.full_config['peers']:
            if peer['id'] == self.config['id']:
                break
            peer_host, peer_port = peer['public_addr']
            await self.start_connection(peer_host, peer_port, self.configs[peer['id']])
        await super().start()

    @staticmethod
    def compute_mutation(account: AccountState, amount: float) -> Tuple[bytes, Any]:
        account_next_version = account.version + 1
        account_next_value = account.value + amount
        account_next_account_hash = AccountState.compute_hash(
            account.account, account_next_version, account_next_value)
        account_mutation_hash = TransactionMutation.compute_hash(
            account.hash, account_next_account_hash)
        account_mutation = {
            'hash': account_mutation_hash.hex(),
            'account': account.account,
            'prev_version': account.version,
            'next_version': account_next_version,
            'next_value': account_next_value,
            'next_account_hash': account_next_account_hash.hex()
        }
        return account_next_account_hash, account_mutation

    @on_requested('make-money', peer_type='admin')
    async def make_money_handler(self, data: Any, context: Context) -> Any:
        config = context.peer_config()
        assert config is not None
        assert self.session is not None
        try:
            amount = round(data['amount'], ACCOUNT_PRECISION)
            assert amount > 0.0
        except (AssertionError, TypeError, KeyError) as error:
            raise RpcError(None, 'bad request') from error
        subquery = select(
            AccountState.account,  # type: ignore
            func.max(AccountState.version).label('latest_version')
        ) \
            .where(or_(AccountState.account == 'coinbase',
                       AccountState.account == config['id'])) \
            .group_by(AccountState.account).alias('latest')
        # noinspection PyUnresolvedReferences,PyTypeChecker
        accounts = list((await self.session.execute(
            select(AccountState).join(  # type: ignore
                subquery,
                and_(
                    AccountState.account == subquery.c.account,  # type: ignore
                    AccountState.version == subquery.c.latest_version,  # type: ignore
                ),
            )
        )).scalars())
        try:
            assert len(accounts) == 2
            if accounts[0].account == 'coinbase':
                assert accounts[1].account == config['id']
                coinbase, account = accounts
            else:
                assert accounts[0].account == config['id']
                assert accounts[1].account == 'coinbase'
                account, coinbase = accounts
        except (AssertionError, TypeError, KeyError) as error:
            raise RpcError(None, 'account does not exist') from error

        coinbase_mutation_hash, coinbase_mutation = self.compute_mutation(coinbase, amount)
        account_mutation_hash, account_mutation = self.compute_mutation(account, amount)
        timestamp = datetime.utcnow()
        endorser = self.config['id']
        signature = Transaction.compute_signature(
            self.private_key, endorser, timestamp,
            [coinbase_mutation_hash, account_mutation_hash])
        block_hash = Transaction.compute_hash(
            endorser, signature, timestamp,
            [coinbase_mutation_hash, account_mutation_hash])
        return {
            'hash': block_hash.hex(),
            'endorser': endorser,
            'signature': signature.hex(),
            'timestamp': timestamp.isoformat(),
            'mutations': [
                coinbase_mutation,
                account_mutation,
            ]
        }

    @on_requested('transfer-money', peer_type='admin')
    @on_requested('transfer-money', peer_type='client')
    async def transfer_money_handler(self, temp_data: Any, context: Context) -> Any:
        config = context.peer_config()
        assert config is not None
        assert self.session is not None
        try:
            data = []
            targets = set()
            assert isinstance(temp_data, list)
            assert temp_data  # at least one item
            total_amount = 0.0
            for item in temp_data:
                amount = item['amount']
                assert isinstance(amount, float)
                assert amount > 0.0
                total_amount += amount
                amount = round(amount, ACCOUNT_PRECISION)
                target = item['target']
                assert isinstance(target, str)
                assert target not in ('coinbase', config['id'])
                assert target not in targets
                targets.add(target)
                data.append({
                    'amount': amount,
                    'target': target,
                })
        except (AssertionError, KeyError) as error:
            raise RpcError(None, 'bad request') from error
        subquery = select(
            AccountState.account,  # type: ignore
            func.max(AccountState.version).label('latest_version')
        ) \
            .where(AccountState.account.in_([config['id'], *targets])) \
            .group_by(AccountState.account).alias('latest')
        # noinspection PyUnresolvedReferences,PyTypeChecker
        accounts = list((await self.session.execute(
            select(AccountState).join(  # type: ignore
                subquery,
                and_(
                    AccountState.account == subquery.c.account,  # type: ignore
                    AccountState.version == subquery.c.latest_version,  # type: ignore
                ),
            )
        )).scalars())
        if len(accounts) != len(targets) + 1:
            raise RpcError(None, 'account does not exist')
        accounts_map: Dict[str, AccountState] = {account.account: account for account in accounts}
        if total_amount > accounts_map[config['id']].value:
            raise RpcError(None, 'no enough money')
        mutations: List[Tuple[bytes, Any]] = [
            self.compute_mutation(accounts_map[config['id']], -total_amount)
        ]
        for item in data:
            mutations.append(self.compute_mutation(
                accounts_map[item['target']], item['amount']))
        mutation_hashs = [mutation_hash for mutation_hash, _ in mutations]
        timestamp = datetime.utcnow()
        endorser = self.config['id']
        signature = Transaction.compute_signature(
            self.private_key, endorser, timestamp, mutation_hashs)
        block_hash = Transaction.compute_hash(
            endorser, signature, timestamp, mutation_hashs)
        return {
            'hash': block_hash.hex(),
            'endorser': endorser,
            'signature': signature.hex(),
            'timestamp': timestamp.isoformat(),
            'mutations': [mutation for _, mutation in mutations]
        }
