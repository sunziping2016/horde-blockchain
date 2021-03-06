from datetime import datetime
from typing import Any

from horde.models import AccountState, TransactionMutation, Transaction, Blockchain
from horde.processors.router import Router, processor, on_requested, Context


class WrongHash(Exception):
    pass


class WrongSignature(Exception):
    pass


@processor
class NodeProcessor(Router):

    @staticmethod
    def check_valid_account_state(account: str, data: Any) -> Any:
        assert isinstance(data, dict)
        account_hash = data['hash']
        assert isinstance(account_hash, str)
        account_hash = bytes.fromhex(account_hash)
        version = data['version']
        assert isinstance(version, int)
        value = data['value']
        assert isinstance(value, (int, float))
        value = float(value)
        computed_account_hash = AccountState.compute_hash(account, version, value)
        if computed_account_hash != account_hash:
            raise WrongHash()
        return {
            'hash': account_hash,
            'version': version,
            'value': value,
        }

    @staticmethod
    def serialize_account_state(data) -> Any:
        return {
            'hash': data['hash'].hex(),
            'version': data['version'],
            'value': data['value'],
        }

    @staticmethod
    def check_valid_mutation(data: Any) -> Any:
        assert isinstance(data, dict)
        mutation_hash = data['hash']
        assert isinstance(mutation_hash, str)
        mutation_hash = bytes.fromhex(mutation_hash)
        account = data['account']
        assert isinstance(account, str)
        prev_account_state = NodeProcessor.check_valid_account_state(
            account, data['prev_account_state'])
        next_account_state = NodeProcessor.check_valid_account_state(
            account, data['next_account_state'])
        assert next_account_state['version'] == prev_account_state['version'] + 1
        computed_mutation_hash = TransactionMutation.compute_hash(
            prev_account_state['hash'], next_account_state['hash'])
        if computed_mutation_hash != mutation_hash:
            raise WrongHash()
        return {
            'hash': mutation_hash,
            'account': account,
            'prev_account_state': prev_account_state,
            'next_account_state': next_account_state,
        }

    @staticmethod
    def serialize_mutation(data) -> Any:
        return {
            'hash': data['hash'].hex(),
            'account': data['account'],
            'prev_account_state': NodeProcessor.serialize_account_state(data['prev_account_state']),
            'next_account_state': NodeProcessor.serialize_account_state(data['next_account_state']),
        }

    def check_valid_transaction(self, data: Any) -> Any:
        assert isinstance(data, dict)
        transaction_hash = data['hash']
        assert isinstance(transaction_hash, str)
        transaction_hash = bytes.fromhex(transaction_hash)
        endorser = data['endorser']
        assert isinstance(endorser, str)
        assert endorser in self.public_keys
        signature = data['signature']
        assert isinstance(signature, str)
        signature = bytes.fromhex(signature)
        timestamp = data['timestamp']
        assert isinstance('timestamp', str)
        timestamp = datetime.fromisoformat(timestamp)
        temp_mutations = data['mutations']
        assert isinstance(temp_mutations, list)
        mutations = [NodeProcessor.check_valid_mutation(mutation)
                     for mutation in temp_mutations]
        mutation_hashs = [mutation['hash'] for mutation in mutations]
        if not Transaction.verify_signature(signature, self.public_keys[endorser],
                                            endorser, timestamp, mutation_hashs):
            raise WrongSignature
        computed_transaction_hash = Transaction.compute_hash(
            endorser, signature, timestamp, mutation_hashs)
        if computed_transaction_hash != transaction_hash:
            raise WrongHash()
        return {
            'hash': transaction_hash,
            'endorser': endorser,
            'signature': signature,
            'timestamp': timestamp,
            'mutations': mutations,
        }

    @staticmethod
    def serialize_transaction(data) -> Any:
        return {
            'hash': data['hash'].hex(),
            'endorser': data['endorser'],
            'signature': data['signature'].hex(),
            'timestamp': data['timestamp'].isoformat(),
            'mutations': [NodeProcessor.serialize_mutation(mutation)
                          for mutation in data['mutations']],
        }

    def check_valid_blockchain(self, data: Any) -> Any:
        block_hash = data['hash']
        assert isinstance(block_hash, str)
        block_hash = bytes.fromhex(block_hash)
        prev_block_hash = data['prev_hash']
        assert isinstance(prev_block_hash, str)
        prev_block_hash = bytes.fromhex(prev_block_hash)
        timestamp = data['timestamp']
        assert isinstance('timestamp', str)
        timestamp = datetime.fromisoformat(timestamp)
        number = data['number']
        assert isinstance(number, int)
        temp_transactions = data['transactions']
        assert isinstance(temp_transactions, list)
        transactions = [self.check_valid_transaction(transaction)
                        for transaction in temp_transactions]
        transaction_hashs = [transaction['hash'] for transaction in transactions]
        computed_block_hash = Blockchain.compute_hash(
            prev_block_hash, timestamp, number, transaction_hashs)
        if computed_block_hash != block_hash:
            raise WrongHash()
        return {
            'hash': block_hash,
            'prev_hash': prev_block_hash,
            'timestamp': timestamp,
            'number': number,
            'transactions': transactions
        }

    @staticmethod
    def serialize_blockchain(data) -> Any:
        return {
            'hash': data['hash'].hex(),
            'prev_hash': data['prev_hash'].hex(),
            'timestamp': data['timestamp'].isoformat(),
            'number': data['number'],
            'transactions': [NodeProcessor.serialize_transaction(transaction)
                             for transaction in data['transactions']],
        }

    @on_requested('who-are-you')
    async def who_are_you_handler(self, data: Any, context: Context) -> Any:
        return self.config['id']
