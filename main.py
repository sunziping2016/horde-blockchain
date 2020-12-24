# pylint: disable=unused-import
import argparse
import horde.sm_tls


def init() -> None:
    print("INIT")


def start() -> None:
    print("Started the app!")


def client():
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
    sub_parsers = main_parser.add_subparsers(title="command", help="available sub-commands")
    # init
    parser_init = sub_parsers.add_parser("init", help="init the horde blockchain")
    parser_init.add_argument("--config", dest="conf", type=str,
                             help="The configuration file, in yaml format.")
    parser_init.set_defaults(func=init)
    # start
    parser_start = sub_parsers.add_parser("start", help="start the server of the horde blockchain")
    parser_start.set_defaults(func=start)
    # client
    parser_client = sub_parsers.add_parser("client", help="start the client the horde blockchain")
    parser_client.add_argument("--open", action="store_true", help="open the web page")
    parser_client.set_defaults(func=client)

    args = main_parser.parse_args()
    args.func()


if __name__ == '__main__':
    main()
