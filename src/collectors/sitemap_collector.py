
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from datetime import datetime, timezone


HEADERS = {
    "User-Agent": "CompetitorContentMonitor/1.0"
}

TIMEOUT = 20
MAX_SITEMAPS = 10


def fetch_xml(url):
    """Download XML securely and parse it."""
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )
    response.raise_for_status()

    return ET.fromstring(response.content)


def get_tag_name(tag):
    """Remove the XML namespace from a tag name."""
    return tag.split("}")[-1].lower()


def discover_sitemap_urls(website_url):
    """
    Check common sitemap locations and robots.txt
    to discover sitemap URLs.
    """
    parsed = urlparse(website_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    candidates = [
        f"{base_url}/sitemap.xml",
        f"{base_url}/sitemap_index.xml",
        f"{base_url}/sitemap-index.xml"
    ]

    robots_url = f"{base_url}/robots.txt"

    try:
        response = requests.get(
            robots_url,
            headers=HEADERS,
            timeout=TIMEOUT
        )
        if response.ok:
            for line in response.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    if sitemap_url:
                        candidates.insert(0, sitemap_url)
    except requests.RequestException:
        pass

    # Preserve order while removing duplicate candidates.
    return list(dict.fromkeys(candidates))


def parse_sitemap(sitemap_url, visited=None, max_sitemaps=MAX_SITEMAPS):
    """
    Parse a sitemap or sitemap index.

    Returns URL records with last-modified dates where
    provided. Sitemap indexes are followed recursively,
    subject to a maximum number of sitemap documents.
    """
    if visited is None:
        visited = set()

    if sitemap_url in visited or len(visited) >= max_sitemaps:
        return []

    visited.add(sitemap_url)

    try:
        root = fetch_xml(sitemap_url)
    except (requests.RequestException, ET.ParseError, ValueError) as error:
        print(f"Could not read sitemap {sitemap_url}: {error}")
        return []

    root_type = get_tag_name(root.tag)
    records = []

    if root_type not in ("urlset", "sitemapindex"):
        print(f"Unsupported sitemap format: {sitemap_url}")
        return []

    for element in root:
        element_type = get_tag_name(element.tag)
        values = {
            get_tag_name(child.tag): (child.text or "").strip()
            for child in element
        }

        if root_type == "sitemapindex" and element_type == "sitemap":
            child_sitemap = values.get("loc")
            if child_sitemap:
                records.extend(
                    parse_sitemap(
                        child_sitemap,
                        visited=visited,
                        max_sitemaps=max_sitemaps
                    )
                )

        elif root_type == "urlset" and element_type == "url":
            page_url = values.get("loc")
            if page_url:
                records.append({
                    "url": page_url,
                    "last_modified": values.get("lastmod") or None,
                    "source_sitemap": sitemap_url
                })

    return records


def collect_sitemap_urls(website_url):
    """
    Discover and parse available sitemaps for a website.
    Returns unique page URLs and their sitemap metadata.
    """
    sitemap_urls = discover_sitemap_urls(website_url)
    all_records = []
    visited = set()

    for sitemap_url in sitemap_urls:
        if len(visited) >= MAX_SITEMAPS:
            break

        records = parse_sitemap(
            sitemap_url,
            visited=visited,
            max_sitemaps=MAX_SITEMAPS
        )
        all_records.extend(records)

    # Deduplicate page URLs across multiple sitemaps.
    unique_records = {}
    for record in all_records:
        unique_records.setdefault(record["url"], record)

    return list(unique_records.values())


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python src/collectors/sitemap_collector.py "
            "<website_url>"
        )
        sys.exit(1)

    website_url = sys.argv[1]

    try:
        records = collect_sitemap_urls(website_url)
        print(f"\nDiscovered {len(records)} unique URLs.")

        for index, record in enumerate(records[:20], start=1):
            print(f"\n{index}. {record['url']}")
            print(f"   Last modified: {record['last_modified']}")

        if len(records) > 20:
            print(f"\n...and {len(records) - 20} more URLs.")

    except Exception as error:
        print(f"Sitemap collection failed: {error}")
        sys.exit(1)