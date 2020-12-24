import argparse
import asyncio
import os
from datetime import datetime

import yaml
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession  # type: ignore

from horde.models import Base, AccountState, Blockchain


async def init(args: argparse.Namespace) -> None:
    with open(args.config) as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    timestamp = datetime.utcnow()
    prev_blockchain_hash = bytes(32)
    for peer in config['peers']:
        assert peer['id'] != 'coinbase', 'peer id cannot be coinbase'
        os.makedirs(peer['root'], exist_ok=True)
        # TODO: create key pairs for all nodes (peers and clients)
        engine = create_async_engine('sqlite:///' + os.path.join(peer['root'], 'sqlite.db'))
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        async with AsyncSession(engine) as session:
            async with session.begin():
                session.add_all([
                    AccountState(
                        account=node['id'], version=0, value=0.0,
                        hash=AccountState.compute_hash(account=node['id'], version=1, value=0.0))
                    for node in [{
                        'id': 'coinbase'
                    }] + config['peers'] + config['clients']
                ])
                session.add(
                    Blockchain(
                        prev_hash=prev_blockchain_hash, timestamp=timestamp, number=1,
                        hash=Blockchain.compute_hash(
                            prev_hash=prev_blockchain_hash, timestamp=timestamp, number=1,
                            transactions=[]
                        )
                    )
                )


async def start(args: argparse.Namespace) -> None:
    print("Started the app!")


async def client(args: argparse.Namespace):
    print("This is the client!")


def parse_extra(parser, namespace):
    namespaces = []
    extra = namespace.extra
    while extra:
        n = parser.parse_args(extra)
        extra = n.extra
        namespaces.append(n)
    return namespaces


def main():
    main_parser = argparse.ArgumentParser()
    main_parser.add_argument("--config", type=str, default='./config.yaml',
                             help="The configuration file, in yaml format.")
    sub_parsers = main_parser.add_subparsers(title="command", help="available sub-commands")
    # init
    parser_init = sub_parsers.add_parser("init", help="init the horde blockchain")
    parser_init.set_defaults(func=init)
    # start
    parser_start = sub_parsers.add_parser("start", help="start the server of the horde blockchain")
    parser_start.set_defaults(func=start)
    # client
    parser_client = sub_parsers.add_parser("client", help="start the client the horde blockchain")
    parser_client.add_argument("--open", action="store_true", help="open the web page")
    parser_client.set_defaults(func=client)

    args = main_parser.parse_args()
    if 'func' in args:
        asyncio.run(args.func(args))


if __name__ == '__main__':
    main()
