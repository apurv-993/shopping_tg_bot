import re
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse


def clean_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_brand(title):
    if not title:
        return ""

    # Usually the first word is the brand
    words = title.split()

    if words:
        return words[0]

    return ""


def extract_specifications(title):
    if not title:
        return []

    specs = []

    patterns = [
        r"\b\d+\s*GB\b",
        r"\b\d+\s*TB\b",
        r"\b\d+\s*MB\b",
        r"\b\d+\s*inch\b",
        r"\b\d+(?:\.\d+)?\s*inch\b",
        r"\b\d+\s*mm\b",
        r"\b\d+\s*cm\b",
        r"\b\d+\s*kg\b",
        r"\b\d+\s*mAh\b",
        r"\b\d+\s*W\b",
        r"\b\d+\s*Hz\b",
        r"\b\d+\s*MP\b",
        r"\bsize\s*\d+(?:\.\d+)?\b",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, title, flags=re.IGNORECASE)

        for match in matches:
            match = clean_text(match).lower()

            if match not in specs:
                specs.append(match)

    return specs


async def extract_product(url):
    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
                )
            }
        ) as client:

            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Try OpenGraph title
        title = ""

        og_title = soup.find("meta", property="og:title")

        if og_title:
            title = og_title.get("content", "")

        # Try Twitter title
        if not title:
            twitter_title = soup.find("meta", attrs={"name": "twitter:title"})

            if twitter_title:
                title = twitter_title.get("content", "")

        # Try normal HTML title
        if not title and soup.title:
            title = soup.title.get_text()

        title = clean_text(title)

        # Extract price if available
        price = None

        price_meta = soup.find(
            "meta",
            attrs={"property": "product:price:amount"}
        )

        if price_meta:
            price = price_meta.get("content")

        if not price:
            price_meta = soup.find(
                "meta",
                attrs={"name": "price"}
            )

            if price_meta:
                price = price_meta.get("content")

        domain = urlparse(url).netloc.lower()

        brand = extract_brand(title)
        specifications = extract_specifications(title)

        return {
            "title": title,
            "brand": brand,
            "specifications": specifications,
            "price": price,
            "domain": domain,
            "url": url
        }

    except Exception as e:
        print("Product extraction error:", e)

        return {
            "title": "",
            "brand": "",
            "specifications": [],
            "price": None,
            "domain": "",
            "url": url
        }