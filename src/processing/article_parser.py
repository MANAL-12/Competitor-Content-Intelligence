
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


HEADERS = {
    "User-Agent": "CompetitorContentMonitor/1.0"
}

TIMEOUT = 20


def get_meta_content(soup, names):
    """Return the first matching metadata content."""
    for name in names:
        tag = soup.find("meta", attrs={"property": name})
        if not tag:
            tag = soup.find("meta", attrs={"name": name})

        if tag and tag.get("content"):
            return tag["content"].strip()

    return None


def extract_article_details(url):
    """Extract basic article metadata from a webpage."""
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Prefer Open Graph title, then the page's title tag.
    title = get_meta_content(soup, ["og:title"])
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)

    description = get_meta_content(
        soup,
        ["og:description", "description"]
    )

    author = get_meta_content(
        soup,
        ["author", "article:author"]
    )

    published_at = get_meta_content(
        soup,
        [
            "article:published_time",
            "datePublished",
            "pubdate"
        ]
    )

    image_url = get_meta_content(
        soup,
        ["og:image", "twitter:image"]
    )

    # Fall back to a visible main heading if metadata is absent.
    if not title:
        heading = soup.find("h1")
        if heading:
            title = heading.get_text(" ", strip=True)

    return {
        "title": title or "Untitled",
        "url": response.url,
        "summary": description or "",
        "author": author,
        "published_at": published_at,
        "image_url": image_url,
        "domain": urlparse(response.url).netloc
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python src/processing/article_parser.py "
            "<article_url>"
        )
        sys.exit(1)

    try:
        details = extract_article_details(sys.argv[1])

        for key, value in details.items():
            print(f"{key}: {value}")

    except requests.RequestException as error:
        print(f"Could not fetch article: {error}")
        sys.exit(1)