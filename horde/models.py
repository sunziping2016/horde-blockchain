from datetime import datetime
from typing import List

from pysmx.SM3 import digest  # type: ignore
from sqlalchemy import Column, Integer, String, Numeric, BLOB, Sequence, ForeignKey, \
    LargeBinary, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

ACCOUNT_PRECISION = 3

Base = declarative_base()


class AccountState(Base):
    __tablename__ = 'account_states'

    account = Column(String, primary_key=True)
    version = Column(Integer, primary_key=True)  # increment from 1
    # should be 0 when version is 1
    value = Column(Numeric(precision=ACCOUNT_PRECISION), nullable=False)
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
    def compute_hash(prev: AccountState, next_: AccountState) -> bytes:
        assert prev.account == next_.account
        return digest(AccountState.compute_hash(prev.account, prev.version, prev.value) +
                      AccountState.compute_hash(next_.account, next_.version, next_.value))


class Transaction(Base):
    __tablename__ = 'transactions'

    hash = Column(BLOB(32), primary_key=True)  # hash(endorser, signature, mutations)
    endorser = Column(String, nullable=False)
    signature = Column(LargeBinary, nullable=False)  # endorser.sign(mutations.hash)
    blockchain_hash = Column(Integer, ForeignKey('blockchains.hash'), nullable=False)

    mutations = relationship('TransactionMutation', uselist=True, back_populates='transaction')
    blockchain = relationship('Blockchain', back_populates='transactions')

    @staticmethod
    def compute_hash(endorser: str, signature: bytes,
                     mutations: List[TransactionMutation]) -> bytes:
        return digest(b'%r,' % endorser + signature +
                      b''.join([mutation.hash for mutation in mutations]))


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
                     transactions: List[Transaction]) -> bytes:
        return digest(prev_hash + b',%s,%d,' % (timestamp.isoformat().encode(), number) +
                      b''.join([transaction.hash for transaction in transactions]))
