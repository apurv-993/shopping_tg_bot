import re
import httpx

from config import SERPAPI_KEY


def create_search_queries(title):
    """
    Create multiple search queries from the product title.
    The bot will try more specific queries first and
    broader queries if no results are found.
    """

    title = title.lower()

    # Remove shopping/marketing words
    remove_words = {
        "buy",
        "online",
        "price",
        "best",
        "new",
        "latest",
        "offer",
        "offers",
        "sale",
        "free",
        "delivery",
        "india",
        "amazon",
        "available",
        "original",
        "genuine",
        "shop",
        "shopping"
    }

    words = re.findall(r"[a-z0-9]+", title)

    useful_words = []

    for word in words:
        if word not in remove_words:
            useful_words.append(word)

    queries = []

    # Query 1: first 10 useful words
    if len(useful_words) >= 10:
        queries.append(" ".join(useful_words[:10]))

    # Query 2: first 7 useful words
    if len(useful_words) >= 7:
        queries.append(" ".join(useful_words[:7]))

    # Query 3: first 5 useful words
    if len(useful_words) >= 5:
        queries.append(" ".join(useful_words[:5]))

    # Query 4: first 4 useful words
    if len(useful_words) >= 4:
        queries.append(" ".join(useful_words[:4]))

    # Remove duplicate queries
    final_queries = []

    for query in queries:
        if query and query not in final_queries:
            final_queries.append(query)

    return final_queries


async def search_single_query(query):
    """
    Search Google Shopping for one query.
    """

    print(f"Trying shopping query: {query}")

    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": SERPAPI_KEY,
        "gl": "in",
        "hl": "en",
        "num": 20
    }

    try:

        async with httpx.AsyncClient(timeout=20) as client:

            response = await client.get(
                "https://serpapi.com/search.json",
                params=params
            )

            response.raise_for_status()

            data = response.json()

        results = []

        for item in data.get("shopping_results", []):

            title = item.get("title", "")

            if not title:
                continue

            results.append({
                "title": title,
                "price": item.get("price"),
                "extracted_price": item.get("extracted_price"),
                "source": item.get("source", ""),
                "link": (
                    item.get("link")
                    or item.get("product_link")
                    or ""
                ),
                "product_link": item.get("product_link", ""),
                "thumbnail": item.get("thumbnail"),
                "rating": item.get("rating"),
                "reviews": item.get("reviews")
            })

        return results

    except Exception as e:

        print(f"Search error for '{query}': {e}")

        return []


async def search_products(title):
    """
    Search using multiple progressively broader queries.
    """

    queries = create_search_queries(title)

    all_results = []

    for query in queries:

        results = await search_single_query(query)

        if results:

            all_results.extend(results)

            # Once we have results, we can stop.
            break

    # Remove duplicate products
    unique_results = {}

    for product in all_results:

        key = (
            product.get("source", "").lower(),
            product.get("title", "").lower()
        )

        if key not in unique_results:
            unique_results[key] = product

    return list(unique_results.values())