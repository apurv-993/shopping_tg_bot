import re
from rapidfuzz.fuzz import token_set_ratio


STOP_WORDS = {
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
    "shopping",
}


def normalize(text):
    text = text.lower()

    text = re.sub(r"[^a-z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    words = text.split()

    words = [
        word
        for word in words
        if word not in STOP_WORDS
    ]

    return " ".join(words)


def get_core_title(title):
    """
    Many shopping titles contain the actual product name
    before a | separator, followed by marketing/specification text.
    """

    title = title.strip()

    if "|" in title:
        title = title.split("|")[0]

    return normalize(title)


def extract_specifications(text):

    text = text.lower()

    patterns = [
        r"\b\d+\s*gb\b",
        r"\b\d+\s*tb\b",
        r"\b\d+\s*mb\b",
        r"\b\d+(?:\.\d+)?\s*inch\b",
        r"\b\d+\s*mah\b",
        r"\b\d+\s*hz\b",
        r"\b\d+\s*w\b",
        r"\b\d+\s*mp\b",
        r"\bsize\s*\d+(?:\.\d+)?\b",
        r"\b\d+\s*kg\b",
        r"\b\d+\s*mm\b",
        r"\b\d+\s*cm\b",
    ]

    specifications = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        for match in matches:

            match = re.sub(
                r"\s+",
                " ",
                match
            ).strip()

            if match not in specifications:
                specifications.append(match)

    return specifications


def product_similarity(original_title, candidate_title):

    original_core = get_core_title(original_title)

    candidate_core = get_core_title(candidate_title)

    if not original_core or not candidate_core:
        return 0

    # Compare the actual product names
    title_score = token_set_ratio(
        original_core,
        candidate_core
    )

    # Compare specifications
    original_specs = set(
        extract_specifications(original_title)
    )

    candidate_specs = set(
        extract_specifications(candidate_title)
    )

    if original_specs and candidate_specs:

        matching_specs = (
            original_specs.intersection(candidate_specs)
        )

        specification_score = (
            len(matching_specs)
            / min(
                len(original_specs),
                len(candidate_specs)
            )
        ) * 100

    else:

        specification_score = 50

    # Check important words in the core product name
    original_words = set(
        original_core.split()
    )

    candidate_words = set(
        candidate_core.split()
    )

    if original_words:

        common_words = (
            original_words.intersection(candidate_words)
        )

        word_match_score = (
            len(common_words)
            / len(original_words)
        ) * 100

    else:

        word_match_score = 0

    # Final score
    final_score = (
        title_score * 0.50
        + word_match_score * 0.30
        + specification_score * 0.20
    )

    return round(
        max(0, min(100, final_score)),
        1
    )


def filter_and_sort_products(
    original_title,
    products,
    minimum_score=65
):

    matched = []

    for product in products:

        candidate_title = product.get(
            "title",
            ""
        )

        if not candidate_title:
            continue

        score = product_similarity(
            original_title,
            candidate_title
        )

        product["match_score"] = score

        if score >= minimum_score:

            matched.append(product)

    # Remove duplicates
    unique = {}

    for product in matched:

        key = (
            product.get(
                "source",
                ""
            ).lower(),

            product.get(
                "title",
                ""
            ).lower()
        )

        if key not in unique:

            unique[key] = product

    matched = list(
        unique.values()
    )

    # Sort by numeric price
    def get_price(product):

        price = product.get(
            "extracted_price"
        )

        if price is not None:

            try:
                return float(price)

            except (ValueError, TypeError):
                pass

        price_text = product.get(
            "price",
            ""
        )

        numbers = re.findall(
            r"[\d,]+(?:\.\d+)?",
            str(price_text)
        )

        if not numbers:
            return float("inf")

        try:

            return float(
                numbers[0].replace(
                    ",",
                    ""
                )
            )

        except ValueError:

            return float("inf")

    matched.sort(
        key=get_price
    )

    return matched