import asyncio

from shopping_search import search_products


async def main():

    query = input("Enter product name: ")

    print("\nSearching...\n")

    results = await search_products(query)

    if not results:
        print("No results found.")
        return

    for i, product in enumerate(results, 1):

        print(f"{i}. {product['title']}")
        print(f"   Price: {product['price']}")
        print(f"   Store: {product['source']}")
        print(f"   Link: {product['link']}")
        print()


asyncio.run(main())