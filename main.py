import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

import yaml
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession  # type: ignore

from horde.models import Base, AccountState, Blockchain
from horde.processors import processor_factory


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
    with open(args.config) as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    if args.node is None:
        processes = []
        for peer in config['peers']:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                *sys.argv,
                '--node',
                peer['id'],
            )
            await asyncio.sleep(0.1)
            processes.append(process)
        await asyncio.gather(*[process.wait() for process in processes])
    else:
        this_config = None
        all_configs = {}
        upstreams = set()
        for peer in config['peers']:
            all_configs[peer['id']] = peer
            if peer['id'] == args.node:
                this_config = peer
            elif this_config is None:
                upstreams.add(peer['id'])
        for client_ in config['clients']:
            all_configs[client_['id']] = client_
        if this_config is None:
            print('invalid peer id `%s\'' % args.node, file=sys.stderr)
            return
        router = processor_factory(this_config['type'])(config=this_config, configs=all_configs,
                                                        upstreams=upstreams)
        await router.start()


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
    main_parser.add_argument("--verbose", action="store_true", help="enable verbose logging")
    main_parser.add_argument("--config", type=str, default='./config.yaml',
                             help="The configuration file, in yaml format.")
    sub_parsers = main_parser.add_subparsers(title="command", help="available sub-commands")
    # init
    parser_init = sub_parsers.add_parser("init", help="init the horde blockchain")
    parser_init.set_defaults(func=init)
    # start
    parser_start = sub_parsers.add_parser("start", help="start the server of the horde blockchain")
    parser_start.add_argument('--node',
                              help='the node to start, start all nodes if not provided')
    parser_start.set_defaults(func=start)
    # client
    parser_client = sub_parsers.add_parser("client", help="start the client the horde blockchain")
    parser_client.add_argument("--open", action="store_true", help="open the web page")
    parser_client.set_defaults(func=client)

    args = main_parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    if 'func' in args:
        asyncio.run(args.func(args))


if __name__ == '__main__':
    main()
