import asyncio
import inspect
import json
import logging
import random
import string
import sys
from asyncio import IncompleteReadError, Future
from dataclasses import dataclass
from typing import Dict, Set, Any, Callable, TypeVar, Generic, Optional, Tuple, Awaitable, ClassVar


def random_id(n: int) -> str:
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase +
                                 string.digits) for _ in range(n))


T = TypeVar("T")


@dataclass
class Box(Generic[T]):
    inner: T

    @property
    def unboxed(self) -> T:
        return self.inner


class RpcError(Exception):
    data: Any

    def __init__(self, data, *args, **kwargs):
        super().__init__(args, kwargs)
        self.data = data


# TODO: able to notify, request (broadcast)
#   change id
#   exit
#   get ids (peer), is peer known
#   get all kinds of config (self, peer, all)
class Context:
    router: 'Router'
    peer_id: str
    writer: asyncio.StreamWriter
    change_id_func: Box[Callable[[str], None]]
    set_exit_func: Box[Callable[[bool], None]]

    def __init__(self, router: 'Router',
                 peer_id: str,
                 writer: asyncio.StreamWriter,
                 change_id_func: Callable[[str], None],
                 set_exit_func: Callable[[bool], None]):
        self.router = router
        self.peer_id = peer_id
        self.writer = writer
        self.change_id_func = Box(change_id_func)
        self.set_exit_func = Box(set_exit_func)

    async def request(self, method: str, data: Any = None, peer_id: Optional[str] = None) -> Any:
        request_id = self.router.next_request_id
        self.router.next_request_id += 1
        self.router.requests[request_id] = asyncio.get_running_loop().create_future()
        raw_content = json.dumps({
            'id': request_id,
            'method': method,
            'params': data,
        })
        writer = self.writer if peer_id is None else self.router.writers[peer_id]
        writer.write(b'Content-Length: %d\r\n\r\n%s' % (len(raw_content), raw_content.encode()))
        await writer.drain()
        response = await self.router.requests[request_id]
        if 'result' in response:
            return response['result']
        raise RpcError(response.get('error'), 'error from remote')

    async def notify(self, method: str, data: Any = None, peer_id: Optional[str] = None) -> None:
        raw_content = json.dumps({
            'method': method,
            'params': data,
        })
        writer = self.writer if peer_id is None else self.router.writers[peer_id]
        writer.write(b'Content-Length: %d\r\n\r\n%s' % (len(raw_content), raw_content.encode()))
        await writer.drain()


def processor(cls):
    cls.server_connected_listeners = {}
    cls.client_connected_listeners = {}
    cls.notification_handlers = {}
    cls.request_handlers = {}
    for func_name, _ in inspect.getmembers(cls):
        func = getattr(cls, func_name)
        if hasattr(func, 'on_server_connected'):
            peer_type = func.on_server_connected
            assert peer_type not in cls.server_connected_listeners, 'duplicated handler'
            cls.server_connected_listeners[peer_type] = func
        if hasattr(func, 'on_client_connected'):
            peer_type = func.on_client_connected
            assert peer_type not in cls.client_connected_listeners, 'duplicated handler'
            cls.client_connected_listeners[peer_type] = func
        if hasattr(func, 'on_notified'):
            method, peer_type = func.on_notified
            assert (method, peer_type) not in cls.notification_handlers, 'duplicated handler'
            cls.notification_handlers[method, peer_type] = func
        if hasattr(func, 'on_requested'):
            method, peer_type = func.on_requested
            assert (method, peer_type) not in cls.request_handlers, 'duplicated handler'
            cls.request_handlers[method, peer_type] = func
    return cls


def on_server_connected(peer_type: Optional[str] = None):
    def wrapper(func):
        func.on_server_connected = peer_type
        return func
    return wrapper


def on_client_connected(peer_type: Optional[str] = None):
    def wrapper(func):
        func.on_client_connected = peer_type
        return func
    return wrapper


def on_notified(method: str, peer_type: Optional[str] = None):
    def wrapper(func):
        func.on_notified = method, peer_type
        return func
    return wrapper


def on_requested(method: str, peer_type: Optional[str] = None):
    def wrapper(func):
        func.on_requested = method, peer_type
        return func
    return wrapper


class Router:
    config: Any
    configs: Dict[str, Any]
    upstreams: Set[str]
    enable_listen: bool  # may be set by subclass
    server: Optional[asyncio.AbstractServer]
    next_request_id: int
    requests: Dict[int, Future]
    writers: Dict[str, asyncio.StreamWriter]
    server_connected_listeners: ClassVar[Dict[Optional[str],
                                              Callable[['Router', Context], Awaitable[None]]]] = {}
    client_connected_listeners: ClassVar[Dict[Optional[str],
                                              Callable[['Router', Context], Awaitable[None]]]] = {}
    notification_handlers: ClassVar[Dict[Tuple[str, Optional[str]],
                                         Callable[['Router', Any, Context], Awaitable[None]]]] = {}
    request_handlers: ClassVar[Dict[Tuple[str, Optional[str]],
                                    Callable[['Router', Any, Context], Awaitable[Any]]]] = {}

    def __init__(self, config: Any, configs: Dict[str, Any], upstreams: Set[str]):
        self.config = config
        self.configs = configs
        self.upstreams = upstreams
        self.enable_listen = False
        self.server = None
        self.next_request_id = 0
        self.requests = {}
        self.writers = {}

    async def on_connected(self, id_: str,
                           is_server_connected: bool,
                           reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter) -> None:
        self.writers[id_] = writer
        exit_flag = False

        context: Optional[Context] = None

        def change_id(new_id: str) -> None:
            nonlocal id_
            del self.writers[id_]
            self.writers[new_id] = writer
            id_ = new_id
            assert context is not None
            context.peer_id = new_id

        def set_exit_flag(flag: bool) -> None:
            nonlocal exit_flag
            exit_flag = flag

        context = Context(self, id_, writer, change_id, set_exit_flag)

        listeners = self.server_connected_listeners if is_server_connected \
            else self.client_connected_listeners
        type_ = self.configs[id_]['type'] if id_ in self.configs else None
        if type_ is not None and type_ in listeners:
            asyncio.create_task(listeners[type_](self, context))
        elif None in listeners:
            asyncio.create_task(listeners[None](self, context))

        try:
            while not exit_flag:
                raw_headers = (await reader.readuntil(b'\r\n\r\n')).decode()
                headers = {}
                for header in raw_headers.split('\r\n'):
                    separator_index = header.find(':')
                    if separator_index != -1:
                        headers[header[:separator_index].lower()] = \
                            header[separator_index + 1:].strip()
                if 'content-length' not in headers:
                    print('%s: missing content length' % id_, file=sys.stderr)
                    break
                content_length = int(headers['content-length'])
                raw_content = (await reader.read(content_length)).decode()
                content = json.loads(raw_content)
                logging.debug('%s: receive data: %s', self.config['id'], content)
                if 'id' in content and 'method' in content:
                    # request
                    method = content['method']
                    type_ = self.configs[id_]['type_'] if id_ in self.configs else None
                    handler = None
                    if (method, type_) in self.request_handlers:
                        handler = self.request_handlers[method, type_]
                    elif (method, None) in self.request_handlers:
                        handler = self.request_handlers[method, None]

                    async def run_handler(method, handler, content):
                        request_id = content['id']
                        if handler is None:
                            response = {
                                'id': request_id,
                                'error': RpcError('%s not supported' % method),
                            }
                        else:
                            response = {
                                'id': request_id,
                                'result': await handler(self, content.get('params'), context),
                            }
                        raw_response = json.dumps(response)
                        writer.write(b'Content-Length: %d\r\n\r\n%s' % (
                            len(raw_response), raw_response.encode()))
                        await writer.drain()
                    asyncio.create_task(run_handler(method, handler, content))
                elif 'id' in content:
                    # response
                    response_id = content['id']
                    if response_id in self.requests:
                        self.requests[response_id].set_result(content)
                else:
                    # notification
                    method = content['method']
                    type_ = self.configs[id_]['type'] if id_ in self.configs else None
                    handler = None
                    if (method, type_) in self.notification_handlers:
                        handler = self.notification_handlers[method, type_]
                    elif (method, None) in self.notification_handlers:
                        handler = self.notification_handlers[method, None]
                    if handler is not None:
                        asyncio.create_task(handler(self, content.get('params'), context))
        except IncompleteReadError:
            pass

    async def start(self) -> None:
        futures = []
        if self.enable_listen:
            host, port = self.config['bind_addr']
            self.server = await asyncio.start_server(
                lambda reader, writer: self.on_connected(
                    'unknown:' + random_id(8), False, reader, writer),
                host, port
            )
            futures.append(self.server.serve_forever())
        for upstream in self.upstreams:
            peer = self.configs[upstream]
            peer_host, peer_port = peer['public_addr']
            reader, writer = await asyncio.open_connection(peer_host, peer_port)
            futures.append(self.on_connected(peer['id'], True, reader, writer))
        if futures:
            await asyncio.gather(*futures)
