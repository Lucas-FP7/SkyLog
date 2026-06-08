import asyncio
import logging
from consumer import consume_alerts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting Notifier Service...")
    await consume_alerts()

if __name__ == "__main__":
    asyncio.run(main())
