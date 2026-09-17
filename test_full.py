import asyncio

from product_extractor import extract_product
from shopping_search import search_products
from matcher import filter_and_sort_products


async def main():

    url = input("Paste product URL: ")

    print("\n1. Extracting product...")

    product = await extract_product(url)

    title = product.get("title")

    if not title:
        print("Could not identify product.")
        return

    print("\nProduct found:")
    print(title)

    print("\n2. Searching other stores...")

    results = await search_products(title)

    print(f"Found {len(results)} shopping results.")

    if not results:
        return

    print("\n3. Matching same products...")

    matched = filter_and_sort_products(
        title,
        results,
        minimum_score=65
    )

    if not matched:
        print("\nNo confident matching products found.")
        return

    print("\n========== PRICE COMPARISON ==========\n")

    for i, product in enumerate(matched, 1):

        print(f"{i}. {product['title']}")
        print(f"   Store: {product.get('source')}")
        print(f"   Price: {product.get('price')}")
        print(f"   Match: {product.get('match_score')}%")
        print(f"   Link: {product.get('link')}")
        print()


asyncio.run(main())