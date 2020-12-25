import argparse
import os
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession  # type: ignore

from horde.processors.node import NodeProcessor
from horde.processors.router import processor


@processor
class PeerProcessor(NodeProcessor):
    engine: AsyncEngine
    session: Optional[AsyncSession]

    def __init__(self, config: Any, full_config: Any, args: argparse.Namespace):
        super().__init__(config, full_config, args)
        self.engine = create_async_engine('sqlite:///' +
                                          os.path.join(self.config['root'], 'sqlite.db'))
        self.session = None

    async def start(self) -> None:
        self.session = AsyncSession(self.engine)
        await super().start()
        await self.session.close()
        self.session = None
