import argparse
import asyncio
import logging
import os
import sys
import traceback
from datetime import datetime
from pysmx.SM2 import generate_keypair  # type: ignore

import yaml
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession  # type: ignore

from horde.models import Base, AccountState, Blockchain
from horde.processors import processor_factory


async def init(args: argparse.Namespace) -> None:
    try:
        with open(args.config) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        # Check the config file
        assert 'public_root' in config
        assert isinstance(config['public_root'], str)
        assert 'peers' in config
        assert isinstance(config['peers'], list)
        for peercfg in config['peers']:
            for variable in ['id', 'type', 'root']:
                assert variable in peercfg
                assert isinstance(peercfg[variable], str)
            assert peercfg['id'] != 'coinbase', 'peer id cannot be coinbase'
            for variable in ['bind_addr', 'public_addr']:
                assert variable in peercfg
                assert isinstance(peercfg[variable], list)
                assert isinstance(peercfg[variable][0], str)
                assert isinstance(peercfg[variable][1], int)
        assert 'clients' in config
        assert isinstance(config['clients'], list)
        for clientcfg in config['clients']:
            for variable in ['id', 'type', 'root']:
                assert variable in clientcfg
                assert isinstance(clientcfg[variable], str)
            assert clientcfg['id'] != 'coinbase', 'client id cannot be coinbase'
    except FileNotFoundError:
        print('ERROR in reading config file: ')
        traceback.print_exc()
        return
    except AssertionError:
        print('ERROR in parsing config file: ')
        traceback.print_exc()
        return
    timestamp = datetime.utcnow()
    os.makedirs(config['public_root'], exist_ok=True)
    prev_blockchain_hash = bytes(32)
    for nodecfg in config['peers'] + config['clients']:
        os.makedirs(nodecfg['root'], exist_ok=True)
        generated_key = generate_keypair()
        with open(os.path.join(nodecfg['root'], 'private.key'), 'wb') as private_file_f:
            private_file_f.write(generated_key.privateKey)
        with open(os.path.join(config['public_root'], '{}.pub.key'.format(nodecfg['id'])),
                  'wb') as public_file_f:
            public_file_f.write(generated_key.publicKey)
        if nodecfg['type'] not in ['orderer', 'endorser']:
            continue
        engine = create_async_engine('sqlite:///' + os.path.join(nodecfg['root'], 'sqlite.db'))
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
        logging.debug('%s: started', args.node)
        await router.start()
        logging.debug('%s: stopped', args.node)


async def client(args: argparse.Namespace) -> None:
    print('This is the client!')


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
    main_parser.add_argument('--verbose', action='store_true', help='enable verbose logging')
    main_parser.add_argument('--config', type=str, default='./config.yaml',
                             help='The configuration file, in yaml format.')
    sub_parsers = main_parser.add_subparsers(title='command', help='available sub-commands')
    # init
    parser_init = sub_parsers.add_parser('init', help='init the horde blockchain')
    parser_init.set_defaults(func=init)
    # start
    parser_start = sub_parsers.add_parser('start', help='start the server of the horde blockchain')
    parser_start.add_argument('--node',
                              help='the node to start, start all nodes if not provided')
    parser_start.set_defaults(func=start)
    # client
    parser_client = sub_parsers.add_parser('client', help='start the client the horde blockchain')
    parser_client.add_argument('--open', action='store_true', help='open the web page')
    parser_client.set_defaults(func=client)

    args = main_parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    if 'func' in args:
        asyncio.run(args.func(args))
    else:
        main_parser.print_help()


if __name__ == '__main__':
    main()
