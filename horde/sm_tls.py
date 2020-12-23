"""Provides async reader and writer for TCP client and server with SM encrypted TLS."""
import asyncio
from typing import Tuple, Callable, Awaitable, Dict


class SMTLSStreamReader:
    inner: asyncio.StreamReader

    def __init__(self, inner: asyncio.StreamReader, key: bytes):
        self.inner = inner  # TODO

    async def read(self, n: int = -1) -> bytes:
        return await self.inner.read(n)  # TODO

    async def readuntil(self, separator: bytes = b'n') -> bytes:  # separator may be multi-bytes
        return await self.inner.readuntil(separator)  # TODO


class SMTLSStreamWriter:
    inner: asyncio.StreamWriter

    def __init__(self, inner: asyncio.StreamWriter, key: bytes):
        self.inner = inner  # TODO

    def write(self, data: bytes) -> None:
        self.inner.write(data)  # TODO

    async def drain(self) -> None:
        await self.inner.drain() # TODO

    def close(self) -> None:
        self.inner.close()  # TODO

    async def wait_closed(self) -> None:
        await self.inner.wait_closed() # TODO


class HandshakeError(Exception):
    pass


async def open_sm_tls_connection(
        local_id: str,
        local_private_key: bytes,
        remote_public_key: bytes,
        *args,
        **kwargs,
) -> Tuple[SMTLSStreamReader, SMTLSStreamWriter]:
    reader, writer = await asyncio.open_connection(*args, **kwargs)
    # TODO: add handshake, generate
    key = b''
    return SMTLSStreamReader(reader, key), SMTLSStreamWriter(writer, key)


async def start_sm_tls_server(
        client_connected_cb: Callable[[SMTLSStreamReader, SMTLSStreamWriter], Awaitable[None]],
        local_private_key: bytes,
        remote_public_keys: Dict[str, bytes],  # do not make copy, value may changed
        *args,
        **kwargs,
) -> asyncio.AbstractServer:
    async def callback(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # TODO: add handshake, generate
        key = b''
        await client_connected_cb(SMTLSStreamReader(reader, key), SMTLSStreamWriter(writer, key))
    return await asyncio.start_server(callback, *args, **kwargs)
