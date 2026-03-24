import asyncio
from telethon import TelegramClient
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate

API_ID = 123456
API_HASH = "hash"

proxy = ("38.244.208.135", 443, "ee79612e7275212a7b4990f03cb10f40")

async def worker(i):
    try:
        client = TelegramClient(
            f"session_{i}",
            API_ID,
            API_HASH,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=proxy
        )

        await client.connect()
        await client.get_me()
        await client.disconnect()

        return True
    except:
        return False


async def main():

    connections = 300

    tasks = [worker(i) for i in range(connections)]
    results = await asyncio.gather(*tasks)

    print("Success:", sum(results))
    print("Fail:", connections - sum(results))


asyncio.run(main())
