import asyncio
import string
import unittest
from typing import Tuple

from pysmx.SM2 import generate_keypair  # type: ignore

from horde.sm_tls import open_sm_tls_connection, SMTLSStreamWriter, SMTLSStreamReader, \
    start_sm_tls_server, HandshakeError


class SMTLSTestCase(unittest.TestCase):
    key_pair1: Tuple[bytes, bytes]
    key_pair2: Tuple[bytes, bytes]
    key_pair3: Tuple[bytes, bytes]

    def setUp(self) -> None:
        self.key_pair1 = generate_keypair()
        self.key_pair2 = generate_keypair()
        self.key_pair3 = generate_keypair()

    @staticmethod
    async def echo_server(reader: SMTLSStreamReader, writer: SMTLSStreamWriter) -> None:
        part_a = await reader.read(21)
        part_b = await reader.readuntil(b'\n')
        content = part_a + part_b
        writer.write(content)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    @staticmethod
    async def echo_client(reader: SMTLSStreamReader, writer: SMTLSStreamWriter) -> bool:
        content = (string.ascii_lowercase + string.digits + '\n').encode()
        writer.write(content)
        await writer.drain()
        part_a = await reader.read(11)  # change this number should always be ok
        part_b = await reader.readuntil(b'\n')
        content2 = part_a + part_b
        writer.close()
        await writer.wait_closed()
        return content == content2

    def test_tls_success(self) -> None:
        """Everything should be okay."""
        client_id = 'hello'

        async def test() -> bool:
            host = '127.0.0.1'
            server = await start_sm_tls_server(SMTLSTestCase.echo_server, self.key_pair1[1], {
                client_id: self.key_pair2[0],
            }, host)
            assert server.sockets is not None
            port = server.sockets[0].getsockname()[1]
            async with server:
                reader, writer = await open_sm_tls_connection(
                    client_id, self.key_pair2[1], self.key_pair1[0], host, port)
                return await SMTLSTestCase.echo_client(reader, writer)
        result = asyncio.run(test())
        self.assertTrue(result)

    @unittest.skip("waiting to be implemented")
    def test_tls_fail_on_wrong_client_key(self) -> None:
        """When client offers wrong key, server should reject it"""
        client_id = 'hello'

        async def test() -> bool:
            host = '127.0.0.1'
            server = await start_sm_tls_server(SMTLSTestCase.echo_server, self.key_pair1[1], {
                client_id: self.key_pair2[0],
            }, host)
            assert server.sockets is not None
            port = server.sockets[0].getsockname()[1]
            async with server:
                reader, writer = await open_sm_tls_connection(
                    client_id, self.key_pair3[1], self.key_pair1[0], host, port)
                return await SMTLSTestCase.echo_client(reader, writer)
        self.assertRaises(HandshakeError, lambda: asyncio.run(test()))

    @unittest.skip("waiting to be implemented")
    def test_tls_fail_on_wrong_server_key(self) -> None:
        """When server offers wrong key, client should reject it"""
        client_id = 'hello'

        async def test() -> bool:
            host = '127.0.0.1'
            server = await start_sm_tls_server(SMTLSTestCase.echo_server, self.key_pair3[1], {
                client_id: self.key_pair2[0],
            }, host)
            assert server.sockets is not None
            port = server.sockets[0].getsockname()[1]
            async with server:
                reader, writer = await open_sm_tls_connection(
                    client_id, self.key_pair2[1], self.key_pair1[0], host, port)
                return  await SMTLSTestCase.echo_client(reader, writer)
        self.assertRaises(HandshakeError, lambda: asyncio.run(test()))

    @unittest.skip("waiting to be implemented")
    def test_tls_fail_on_client_not_exist(self) -> None:
        """When client does not exit, server should reject it"""
        async def test() -> bool:
            host = '127.0.0.1'
            server = await start_sm_tls_server(SMTLSTestCase.echo_server, self.key_pair1[1], {
                'hello': self.key_pair2[0],
            }, host)
            assert server.sockets is not None
            port = server.sockets[0].getsockname()[1]
            async with server:
                reader, writer = await open_sm_tls_connection(
                    'world', self.key_pair2[1], self.key_pair1[0], host, port)
                return await SMTLSTestCase.echo_client(reader, writer)
        self.assertRaises(HandshakeError, lambda: asyncio.run(test()))


if __name__ == '__main__':
    unittest.main()
