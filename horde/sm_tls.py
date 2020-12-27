"""Provides async reader and writer for TCP client and server with SM encrypted TLS."""
import asyncio
import os
from typing import Tuple, Callable, Awaitable, Dict

from pysmx.SM2 import Encrypt, Decrypt  # type: ignore
from pysmx.SM4 import Sm4, ENCRYPT, DECRYPT  # type: ignore

IV_DATA = [0x5a] * 16


class SMTLSStreamReader:
    inner: asyncio.StreamReader
    buffer: bytes

    def __init__(self, inner: asyncio.StreamReader, key: bytes):
        self.inner = inner
        self.sm4 = Sm4()
        self.sm4.sm4_set_key(key, DECRYPT)
        self.buffer = b''

    async def readexactly(self, n: int) -> bytes:
        result = self.buffer
        while len(result) < n:
            data_len = int.from_bytes(await self.inner.readexactly(4), byteorder='big')
            data = bytes(self.sm4.sm4_crypt_cbc(IV_DATA, await self.inner.readexactly(data_len)))
            padding = int.from_bytes(data[:1], byteorder='big')
            result += data[1:] if padding == 0 else data[1:-padding]
        self.buffer = result[n:]
        return result[:n]

    async def readuntil(self, separator: bytes = b'\n') -> bytes:  # separator may be multi-bytes
        result = self.buffer
        while result.find(separator) == -1:
            data_len = int.from_bytes(await self.inner.readexactly(4), byteorder='big')
            data = bytes(self.sm4.sm4_crypt_cbc(IV_DATA, await self.inner.readexactly(data_len)))
            padding = int.from_bytes(data[:1], byteorder='big')
            result += data[1:] if padding == 0 else data[1:-padding]
        index = result.find(separator) + len(separator)
        self.buffer = result[index:]
        return result[:index]


class SMTLSStreamWriter:
    inner: asyncio.StreamWriter
    sm4: Sm4

    def __init__(self, inner: asyncio.StreamWriter, key: bytes):
        self.inner = inner
        self.sm4 = Sm4()
        self.sm4.sm4_set_key(key, ENCRYPT)

    def write(self, data: bytes) -> None:
        padding = (15 - len(data)) % 16
        data = padding.to_bytes(1, byteorder='big') + data + b'\0' * padding
        encrypted_data = self.sm4.sm4_crypt_cbc(IV_DATA, data)
        self.inner.write(len(encrypted_data).to_bytes(4, byteorder='big'))
        self.inner.write(bytes(encrypted_data))

    async def drain(self) -> None:
        await self.inner.drain()

    def close(self) -> None:
        self.inner.close()

    async def wait_closed(self) -> None:
        await self.inner.wait_closed()


class HandshakeError(Exception):
    pass


async def open_sm_tls_connection(
        local_id: str,
        local_private_key: bytes,
        remote_public_key: bytes,
        *args,
        **kwargs,
) -> Tuple[SMTLSStreamReader, SMTLSStreamWriter]:
    try:
        reader, writer = await asyncio.open_connection(*args, **kwargs)
        local_random = os.urandom(16)
        handshake = local_id.encode() + local_random
        handshake_encrypted = Encrypt(handshake, remote_public_key, 64)
        writer.write(len(handshake_encrypted).to_bytes(4, byteorder='big'))
        writer.write(handshake_encrypted)
        await writer.drain()
        remote_random_encrypted_len = int.from_bytes(await reader.readexactly(4), byteorder='big')
        remote_random_encrypted = await reader.readexactly(remote_random_encrypted_len)
        remote_random = Decrypt(remote_random_encrypted, local_private_key, 64)
        key = local_random + remote_random
        return SMTLSStreamReader(reader, key), SMTLSStreamWriter(writer, key)
    except (TypeError, asyncio.IncompleteReadError) as error:
        raise HandshakeError from  error


async def start_sm_tls_server(
        client_connected_cb: Callable[[SMTLSStreamReader, SMTLSStreamWriter, str], Awaitable[None]],
        local_private_key: bytes,
        remote_public_keys: Dict[str, bytes],  # do not make copy, value may changed
        *args,
        **kwargs,
) -> asyncio.AbstractServer:
    async def callback(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            handshake_encrypted_len = int.from_bytes(await reader.readexactly(4), byteorder='big')
            handshake_encrypted = await reader.readexactly(handshake_encrypted_len)
            handshake = Decrypt(handshake_encrypted, local_private_key, 64)
            remote_id = handshake[:-16].decode()
            remote_random = handshake[-16:]
            local_random = os.urandom(16)
            local_random_encrypted = Encrypt(local_random, remote_public_keys[remote_id], 64)
            writer.write(len(local_random_encrypted).to_bytes(4, byteorder='big'))
            writer.write(local_random_encrypted)
            await writer.drain()
            key = remote_random + local_random
            await client_connected_cb(SMTLSStreamReader(reader, key),
                                      SMTLSStreamWriter(writer, key),
                                      remote_id)
        except (KeyError, TypeError):
            writer.close()
            await writer.wait_closed()
    return await asyncio.start_server(callback, *args, **kwargs)
