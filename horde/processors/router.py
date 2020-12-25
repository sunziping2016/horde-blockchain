import asyncio
import inspect
import json
import logging
import random
import string
import sys
import traceback
from asyncio import IncompleteReadError, Future, FIRST_COMPLETED
from dataclasses import dataclass
from typing import Dict, Set, Any, Callable, TypeVar, Generic, Optional, Tuple, Awaitable, \
    ClassVar, Type


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


class Context:
    router: 'Router'
    peer_id: str
    change_peer_id_func: Box[Callable[[str], None]]

    def __init__(self, router: 'Router',
                 peer_id: str,
                 change_id_func: Callable[[str], None]):
        self.router = router
        self.peer_id = peer_id
        self.change_peer_id_func = Box(change_id_func)

    def is_peer_unknown(self) -> bool:
        return self.peer_id not in self.router.configs

    def peer_config(self) -> Optional[Any]:
        return self.router.configs.get(self.peer_id)

    def change_peer_id(self, new_id) -> None:
        self.change_peer_id_func.inner(new_id)

    def close_connection(self, peer_id: Optional[str] = None) -> None:
        if peer_id is None:
            peer_id = self.peer_id
        self.router.close_connection(peer_id)

    async def request(self, method: str, data: Any = None, peer_id: Optional[str] = None) -> Any:
        if peer_id is None:
            peer_id = self.peer_id
        return await self.router.request(method, data, peer_id)

    async def notify(self, method: str, data: Any = None, peer_id: Optional[str] = None) -> None:
        if peer_id is None:
            peer_id = self.peer_id
        await self.router.notify(method, data, peer_id)


R = TypeVar('R', bound='Router')


def processor(cls: Type[R]) -> Type[R]:
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


def on_server_connected(
        peer_type: Optional[str] = None
) -> Callable[[Callable[[R, Context], Awaitable[None]]],
              Callable[[R, Context], Awaitable[None]]]:
    def wrapper(
            func: Callable[[R, Context], Awaitable[None]]
    ) -> Callable[[R, Context], Awaitable[None]]:
        # noinspection PyTypeHints
        func.on_server_connected = peer_type  # type: ignore
        return func
    return wrapper


def on_client_connected(
        peer_type: Optional[str] = None
) -> Callable[[Callable[[R, Context], Awaitable[None]]],
              Callable[[R, Context], Awaitable[None]]]:
    def wrapper(
            func: Callable[[R, Context], Awaitable[None]]
    ) -> Callable[[R, Context], Awaitable[None]]:
        # noinspection PyTypeHints
        func.on_client_connected = peer_type  # type: ignore
        return func
    return wrapper


def on_notified(
        method: str, peer_type: Optional[str] = None
) -> Callable[[Callable[[R, Any, Context], Awaitable[None]]],
              Callable[[R, Any, Context], Awaitable[None]]]:
    def wrapper(
            func: Callable[[R, Any, Context], Awaitable[None]]
    ) -> Callable[[R, Any, Context], Awaitable[None]]:
        # noinspection PyTypeHints
        func.on_notified = method, peer_type  # type: ignore
        return func
    return wrapper


def on_requested(
        method: str, peer_type: Optional[str] = None
) -> Callable[[Callable[[R, Any, Context], Awaitable[Any]]],
              Callable[[R, Any, Context], Awaitable[Any]]]:
    def wrapper(
            func: Callable[[R, Any, Context], Awaitable[Any]]
    ) -> Callable[[R, Any, Context], Awaitable[Any]]:
        # noinspection PyTypeHints
        func.on_requested = method, peer_type  # type: ignore
        return func
    return wrapper


class MissingContentLength(Exception):
    pass


class Router:
    config: Any
    configs: Dict[str, Any]
    upstreams: Set[str]
    enable_listen: bool  # may be set by subclass
    server: Optional[asyncio.AbstractServer]
    next_request_id: int
    requests: Dict[int, Future]
    writer_queues: Dict[str, asyncio.Queue]
    shutdown_futures: Dict[str, Future]
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
        self.writer_queues = {}
        self.shutdown_futures = {}

    def close_server(self):
        if self.server is not None:
            self.server.close()

    def close_connection(self, peer_id: str) -> None:
        exit_future = self.shutdown_futures[peer_id]
        if not exit_future.done():
            exit_future.set_result(None)

    async def request(self, method: str, data: Any, peer_id: str) -> Any:
        request_id = self.next_request_id
        writer_queue = self.writer_queues[peer_id]
        self.next_request_id += 1
        self.requests[request_id] = asyncio.get_running_loop().create_future()
        content = {
            'id': request_id,
            'method': method,
            'params': data,
        }
        await writer_queue.put(content)
        response = await self.requests[request_id]
        if 'result' in response:
            return response['result']
        raise RpcError(response.get('error'), 'error from remote')

    async def notify(self, method: str, data: Any, peer_id: str) -> None:
        writer_queue = self.writer_queues[peer_id]
        raw_content = {
            'method': method,
            'params': data,
        }
        await writer_queue.put(raw_content)

    async def on_connected(self, id_: str,
                           is_server_connected: bool,
                           reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter) -> None:
        writer_queue: asyncio.Queue = asyncio.Queue()
        exit_future: Future = Future()
        self.writer_queues[id_] = writer_queue
        self.shutdown_futures[id_] = exit_future
        context: Optional[Context] = None

        def change_peer_id(new_id: str) -> None:
            nonlocal id_
            logging.info('%s: connection change id from %s to %s', self.config['id'], id_, new_id)
            old_future = self.shutdown_futures[id_]
            old_queue = self.writer_queues[id_]
            del self.shutdown_futures[id_]
            del self.writer_queues[id_]
            self.shutdown_futures[new_id] = old_future
            self.writer_queues[new_id] = old_queue
            id_ = new_id
            assert context is not None
            context.peer_id = new_id

        async def read_content() -> Any:
            try:
                raw_headers = (await reader.readuntil(b'\r\n\r\n')).decode()
                headers = {}
                for header in raw_headers.split('\r\n'):
                    separator_index = header.find(':')
                    if separator_index != -1:
                        headers[header[:separator_index].lower()] = \
                            header[separator_index + 1:].strip()
                if 'content-length' not in headers:
                    print('%s: missing content length' % id_, file=sys.stderr)
                    raise MissingContentLength
                content_length = int(headers['content-length'])
                raw_content = (await reader.read(content_length)).decode()
                return json.loads(raw_content)
            except IncompleteReadError:
                logging.error('%s: %s connection closed', self.config['id'], id_)
                return None
            except Exception as error:
                traceback.print_exc()
                raise error

        logging.info('%s: connection from %s started', self.config['id'], id_)
        try:
            context = Context(self, id_, change_peer_id)
            tasks: Set[Future] = set()

            listeners = self.server_connected_listeners if is_server_connected \
                else self.client_connected_listeners
            type_ = self.configs[id_]['type'] if id_ in self.configs else None
            if type_ is not None and type_ in listeners:
                tasks.add(asyncio.create_task(listeners[type_](self, context)))
            elif None in listeners:
                tasks.add(asyncio.create_task(listeners[None](self, context)))

            read_content_task: Optional[asyncio.Task] = asyncio.create_task(read_content())
            get_writer_queue_task = asyncio.create_task(writer_queue.get())

            while True:
                done, _ = await asyncio.wait({
                    *([] if exit_future.done() else [exit_future]),
                    get_writer_queue_task,
                    *([] if read_content_task is None else [read_content_task]),
                    *tasks,
                }, return_when=FIRST_COMPLETED)
                if exit_future in done:
                    await exit_future
                tasks -= done
                if get_writer_queue_task in done:
                    send_content = await get_writer_queue_task
                    raw_send_content = json.dumps(send_content)
                    writer.write(b'Content-Length: %d\r\n\r\n%s' % (
                        len(raw_send_content), raw_send_content.encode()))
                    get_writer_queue_task = asyncio.create_task(writer_queue.get())
                if read_content_task is not None and read_content_task in done:
                    content = await read_content_task
                    if content is None:
                        read_content_task = None
                    else:
                        read_content_task = asyncio.create_task(read_content())
                        logging.debug('%s: receive data: %s', self.config['id'], content)
                        if 'id' in content and 'method' in content:
                            # request
                            method = content['method']
                            type_ = self.configs[id_]['type'] if id_ in self.configs else None
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
                                        'error': '%s not supported' % method,
                                    }
                                else:
                                    try:
                                        response = {
                                            'id': request_id,
                                            'result': await handler(self, content.get('params'),
                                                                    context),
                                        }
                                    except RpcError as error:
                                        response = {
                                            'id': request_id,
                                            'error': error.data,
                                        }
                                await writer_queue.put(response)
                            tasks.add(asyncio.create_task(run_handler(method, handler, content)))
                        elif 'id' in content:
                            # response
                            response_id = content['id']
                            if response_id in self.requests:
                                self.requests[response_id].set_result(content)
                                del self.requests[response_id]
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
                                tasks.add(asyncio.create_task(
                                    handler(self, content.get('params'), context)))
                if (exit_future.done() or read_content_task is None) \
                        and writer_queue.empty() and not tasks:
                    break
            writer.close()
            await writer.wait_closed()
        except Exception as error:
            traceback.print_exc()
            raise error
        finally:
            # await server close
            del self.writer_queues[id_]
            del self.shutdown_futures[id_]
            logging.info('%s: connection from %s stopped', self.config['id'], id_)

    async def start(self) -> None:
        task_queue: asyncio.Queue = asyncio.Queue()

        async def callback(reader, writer):
            await task_queue.put(asyncio.create_task(self.on_connected(
                'unknown:' + random_id(8), False, reader, writer)))
        if self.enable_listen:
            host, port = self.config['bind_addr']
            self.server = await asyncio.start_server(
                callback,
                host, port
            )

            async def start_server():
                try:
                    logging.info('%s: server started', self.config['id'])
                    await self.server.serve_forever()
                except asyncio.CancelledError:
                    pass
                finally:
                    logging.info('%s: server shutdown', self.config['id'])
                    await self.server.wait_closed()
            await task_queue.put(asyncio.create_task(start_server()))
        for upstream in self.upstreams:
            peer = self.configs[upstream]
            peer_host, peer_port = peer['public_addr']
            reader, writer = await asyncio.open_connection(peer_host, peer_port)
            await task_queue.put(asyncio.create_task(
                self.on_connected(peer['id'], True, reader, writer)))
        tasks: Set[asyncio.Task] = set()
        get_task_queue_task = asyncio.create_task(task_queue.get())
        while tasks or not task_queue.empty():
            done, _ = await asyncio.wait({
                *tasks,
                get_task_queue_task,
            }, return_when=FIRST_COMPLETED)
            if get_task_queue_task in done:
                new_task = await get_task_queue_task
                tasks.add(new_task)
                get_task_queue_task = asyncio.create_task(task_queue.get())
            tasks -= done
