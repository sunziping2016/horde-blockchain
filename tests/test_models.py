import asyncio
import unittest

from sqlalchemy.ext.asyncio import create_async_engine  # type: ignore

from horde.models import Base


class ModelsTestCase(unittest.TestCase):

    def test_create_models(self) -> None:  # pylint: disable=no-self-use
        """All models can be created."""
        async def test() -> None:
            engine = create_async_engine('sqlite:///:memory:', echo=True)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        asyncio.run(test())
