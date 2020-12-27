import random
from datetime import datetime
from typing import List, Any

from pysmx.SM2 import Sign, Verify  # type: ignore
from pysmx.SM3 import digest  # type: ignore
from sqlalchemy import Column, Integer, String, Numeric, BLOB, Sequence, ForeignKey, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

ACCOUNT_PRECISION = 3

Base = declarative_base()


class AccountState(Base):
    __tablename__ = 'account_states'

    account = Column(String, primary_key=True)
    version = Column(Integer, primary_key=True)  # increment from 1
    # should be 0 when version is 1
    value = Column(Numeric(precision=ACCOUNT_PRECISION, asdecimal=False), nullable=False)
    hash = Column(BLOB(32), nullable=False)  # hash(account, version, value)

    @staticmethod
    def compute_hash(account: str, version: int, value: float) -> bytes:
        return digest(('%r,%d,%.' + str(ACCOUNT_PRECISION) + 'f') % (account, version, value))


class TransactionMutation(Base):
    __tablename__ = 'transaction_mutations'

    # hash(AccountState(account, prev_version).hash, AccountState(account, next_version).hash)
    hash = Column(BLOB(32), primary_key=True)
    account = Column(Integer, ForeignKey('account_states.account'), nullable=False)
    prev_version = Column(Integer, ForeignKey('account_states.version'), nullable=False)
    next_version = Column(Integer, ForeignKey('account_states.version'), nullable=False)
    transaction_hash = Column(Integer, ForeignKey('transactions.hash'), nullable=False)

    prev_account_state = relationship(
        'AccountState', uselist=False, viewonly=True,
        primaryjoin='and_(TransactionMutation.account==AccountState.account, '
                    'TransactionMutation.prev_version==AccountState.version)')
    next_account_state = relationship(
        'AccountState', uselist=False, viewonly=True,
        primaryjoin='and_(TransactionMutation.account==AccountState.account, '
                    'TransactionMutation.next_version==AccountState.version)')
    transaction = relationship('Transaction', back_populates='mutations')

    @staticmethod
    def compute_hash(prev_hash: bytes, next_hash: bytes) -> bytes:
        return digest(prev_hash + next_hash)

    def serialize(self) -> Any:
        return {
            'hash': self.hash.hex(),
            'account': self.account,
            'prev_account_state': {
                'hash': self.prev_account_state.hash.hex(),
                'version': self.prev_account_state.version,
                'value': self.prev_account_state.value,
            },
            'next_account_state': {
                'hash': self.next_account_state.hash.hex(),
                'version': self.next_account_state.version,
                'value': self.next_account_state.value,
            },
        }


class Transaction(Base):
    __tablename__ = 'transactions'

    # hash(endorser, signature, timestamp, mutations.hash)
    hash = Column(BLOB(32), primary_key=True)
    # endorser.sign(endorser, timestamp, mutations.hash)
    signature = Column(BLOB(64), nullable=False)
    endorser = Column(String, nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False)
    blockchain_hash = Column(Integer, ForeignKey('blockchains.hash'), nullable=False)

    mutations = relationship('TransactionMutation', uselist=True, back_populates='transaction')
    blockchain = relationship('Blockchain', back_populates='transactions')

    @staticmethod
    def compute_hash(endorser: str, signature: bytes, timestamp: datetime,
                     mutations: List[bytes]) -> bytes:
        return digest(b'%r,%s,' % (endorser, timestamp.isoformat().encode()) +
                      signature + b''.join(mutations))

    @staticmethod
    def compute_signature(private_key: bytes, endorser: str,
                          timestamp: datetime, mutations: List[bytes]):
        content = b'%r,%s,' % (endorser, timestamp.isoformat().encode()) + b''.join(mutations)
        return Sign(content, private_key,
                    hex(random.randint(2 ** (8 * 7), 2 ** (8 * 8) - 1))[2:], 64)

    @staticmethod
    def verify_signature(signature: bytes, public_key: bytes, endorser: str,
                         timestamp: datetime, mutations: List[bytes]):
        content = b'%r,%s,' % (endorser, timestamp.isoformat().encode()) + b''.join(mutations)
        return Verify(signature, content, public_key, 64)

    def serialize(self) -> Any:
        # noinspection PyTypeChecker
        return {
            'hash': self.hash.hex(),
            'endorser': self.endorser,
            'signature': self.signature.hex(),
            'timestamp': self.timestamp.isoformat(),
            'mutations': [mutation.serialize() for mutation in self.mutations]  # type: ignore
        }


class Blockchain(Base):
    __tablename__ = 'blockchains'

    # hash(prev_hash, timestamp, number, transactions)
    hash = Column(BLOB(32), primary_key=True, nullable=False)
    prev_hash = Column(BLOB(32), ForeignKey('blockchains.hash'), nullable=False)
    timestamp = Column(TIMESTAMP, nullable=False)
    number = Column(Integer, Sequence('blockchain_number.seq'), index=True, nullable=False)

    transactions = relationship('Transaction', back_populates='blockchain')

    @staticmethod
    def compute_hash(prev_hash: bytes, timestamp: datetime, number: int,
                     transactions: List[bytes]) -> bytes:
        return digest(prev_hash + b',%s,%d,' % (timestamp.isoformat().encode(), number) +
                      b''.join(transactions))

    def serialize(self) -> Any:
        # noinspection PyTypeChecker
        return {
            'hash': self.hash.hex(),
            'prev_hash': self.prev_hash.hex(),
            'timestamp': self.timestamp.isoformat(),
            'number': self.number,
            'transactions': [transaction.serialize()
                             for transaction in self.transactions]  # type: ignore
        }
