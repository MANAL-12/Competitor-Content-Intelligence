
import argparse
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "CompetitorContentMonitor/1.0 (educational project)"
}
TIMEOUT = 15

COMMON_FEEDS = [
    "feed",
    "feed.xml",
    "rss",
    "rss.xml",
    "atom.xml",
]

COMMON_SITEMAPS = [
    "sitemap.xml",
    "sitemap_index.xml",
    "sitemap-index.xml",
]


def normalize_url(url):
    """Add https:// when the user enters a domain without a scheme."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/") + "/"


def fetch_url(url):
    """Request a page and return the response, or None if it fails."""
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        return response
    except requests.RequestException as error:
        print(f"Request failed for {url}: {error}")
        return None


def inspect_homepage(homepage_url):
    """Find feed links and the site's robots.txt sitemap declarations."""
    results = {
        "homepage": homepage_url,
        "feeds": [],
        "sitemaps": [],
        "notes": [],
    }

    response = fetch_url(homepage_url)
    if response is None:
        results["notes"].append("Homepage could not be reached.")
        return results

    if response.status_code >= 400:
        results["notes"].append(
            f"Homepage returned HTTP {response.status_code}."
        )
        return results

    soup = BeautifulSoup(response.text, "html.parser")

    # Look for RSS/Atom links explicitly declared in the HTML.
    for link in soup.find_all("link", href=True):
        rel = link.get("rel", [])
        rel_values = [str(value).lower() for value in rel]
        content_type = link.get("type", "").lower()

        if "alternate" in rel_values and (
            "rss" in content_type or "atom" in content_type
        ):
            results["feeds"].append(
                urljoin(response.url, link["href"])
            )

    # Check robots.txt for sitemap declarations.
    robots_url = urljoin(response.url, "/robots.txt")
    robots_response = fetch_url(robots_url)

    if robots_response and robots_response.status_code == 200:
        for line in robots_response.text.splitlines():
            if line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                if sitemap_url:
                    results["sitemaps"].append(sitemap_url)

    # Check common feed and sitemap paths on the website.
    for path in COMMON_FEEDS:
        candidate = urljoin(response.url, path)
        candidate_response = fetch_url(candidate)
        if candidate_response and candidate_response.status_code == 200:
            content_type = candidate_response.headers.get(
                "Content-Type", ""
            ).lower()
            body_start = candidate_response.text[:500].lower()

            if (
                "xml" in content_type
                or "rss" in content_type
                or "feed" in content_type
                or "<rss" in body_start
                or "<feed" in body_start
            ):
                results["feeds"].append(candidate_response.url)

    for path in COMMON_SITEMAPS:
        candidate = urljoin(response.url, path)
        candidate_response = fetch_url(candidate)
        if candidate_response and candidate_response.status_code == 200:
            content_type = candidate_response.headers.get(
                "Content-Type", ""
            ).lower()
            body_start = candidate_response.text[:500].lower()

            if (
                "xml" in content_type
                or "<urlset" in body_start
                or "<sitemapindex" in body_start
            ):
                results["sitemaps"].append(candidate_response.url)

    # Remove duplicates while preserving discovery order.
    results["feeds"] = list(dict.fromkeys(results["feeds"]))
    results["sitemaps"] = list(dict.fromkeys(results["sitemaps"]))

    return results


def analyze_website(url):
    """Run discovery and suggest which monitoring methods are available."""
    homepage = normalize_url(url)
    results = inspect_homepage(homepage)

    methods = []
    if results["feeds"]:
        methods.append("RSS/Atom")
    if results["sitemaps"]:
        methods.append("Sitemap")

    # Direct-page monitoring remains a possible fallback.
    methods.append("Direct-page monitoring (requires page selection)")

    results["suggested_methods"] = methods
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Discover feeds and sitemaps for a website."
    )
    parser.add_argument(
        "url",
        help="Website URL, for example https://example.com",
    )
    args = parser.parse_args()

    results = analyze_website(args.url)

    print("\n=== Website Analysis ===")
    print(f"Website: {results['homepage']}")

    print("\nRSS/Atom feeds:")
    if results["feeds"]:
        for feed in results["feeds"]:
            print(f"  - {feed}")
    else:
        print("  None discovered")

    print("\nSitemaps:")
    if results["sitemaps"]:
        for sitemap in results["sitemaps"]:
            print(f"  - {sitemap}")
    else:
        print("  None discovered")

    print("\nSuggested monitoring methods:")
    for method in results["suggested_methods"]:
        print(f"  - {method}")

    if results["notes"]:
        print("\nNotes:")
        for note in results["notes"]:
            print(f"  - {note}")


if __name__ == "__main__":
    main()