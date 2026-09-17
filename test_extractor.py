import asyncio
from product_extractor import extract_product


async def main():

    url = input("Paste product URL: ")

    result = await extract_product(url)

    print("\nRESULT:")
    print(result)


asyncio.run(main())