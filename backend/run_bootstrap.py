import asyncio
import logging

from app.utils.database import async_session_factory
from app.ingestion.bootstrap import BootstrapService

logging.basicConfig(level=logging.INFO)

async def main():
    async with async_session_factory() as db:
        bootstrapper = BootstrapService(db)
        await bootstrapper.run()

if __name__ == "__main__":
    asyncio.run(main())
