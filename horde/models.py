from sqlalchemy import Column, Integer, String, Numeric, BLOB, Sequence, ForeignKey, \
    LargeBinary, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

ACCOUNT_PRECISION = 3

Base = declarative_base()


class AccountState(Base):
    __tablename__ = 'account_states'

    account = Column(String, primary_key=True)
    version = Column(Integer, primary_key=True)  # increment from zero
    value = Column(Numeric(precision=ACCOUNT_PRECISION))  # shoule be 0 when version is zero
    hash = Column(BLOB(32))  # hash(account, version, value)


class LatestAccountState(Base):
    __tablename__ = 'latesst_account_statees'

    account = Column(String, primary_key=True)
    latest_version = Column(Integer)


class TransactionMutation(Base):
    __tablename__ = 'transaction_items'

    # hash(AccountState(account, prev_version).hash, AccountState(account, next_version).hash)
    hash = Column(BLOB(32), primary_key=True)
    account = Column(Integer)
    prev_version = Column(Integer)
    next_version = Column(Integer)
    transaction_hash = Column(Integer, ForeignKey('transactions.hash'))

    transaction = relationship('Transaction', back_populates='mutations')


class Transaction(Base):
    __tablename__ = 'transactions'

    hash = Column(BLOB(32), primary_key=True)  # hash(endorser, signature, mutations)
    endorser = Column(String)
    signature = Column(LargeBinary)  # endorser.sign(mutations.hash)
    blockchain_hash = Column(Integer, ForeignKey('blockchains.hash'))

    mutations = relationship('TransactionMutation', back_populates='transaction')
    blockchain = relationship('Blockchain', back_populates='transactions')


class Blockchain(Base):
    __tablename__ = 'blockchains'

    # hash(prev_hash, timestamp, transactions)
    hash = Column(Integer, Sequence('blockchain_hash_seq'), primary_key=True)
    prev_hash = Column(BLOB(32), ForeignKey('blockchains.hash'))
    timestamp = Column(TIMESTAMP)

    transactions = relationship('Transaction', back_populates='blockchain')
