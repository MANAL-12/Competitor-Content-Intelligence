import sys
from pathlib import Path
from urllib.parse import urlparse

# Add the project root so imports work when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.collectors.sitemap_collector import collect_sitemap_urls
from src.processing.article_parser import extract_article_details
from src.database.db import initialize_database, save_article


def monitor_sitemap(website_url, limit=10):
    """
    Discover sitemap URLs, parse a limited number of pages,
    and save their metadata to the SQLite database.
    """
    website_name = urlparse(website_url).netloc or website_url

    print(f"\nStarting sitemap monitoring for: {website_name}")
    print("Discovering sitemap URLs...")

    records = collect_sitemap_urls(website_url)
    print(f"Discovered {len(records)} unique page URLs.")

    if not records:
        print("No sitemap URLs found. Nothing to process.")
        return

    # Limit the first run to avoid fetching hundreds of pages at once.
    records_to_process = records[:limit]
    print(f"Processing up to {len(records_to_process)} pages.")

    new_count = 0
    duplicate_count = 0
    error_count = 0

    for index, record in enumerate(records_to_process, start=1):
        page_url = record["url"]
        print(f"\n[{index}/{len(records_to_process)}] Parsing: {page_url}")

        try:
            article = extract_article_details(page_url)

            # Add source information from the monitored website and sitemap.
            article["source_name"] = website_name
            article["source_type"] = "sitemap"
            article["source_sitemap"] = record.get("source_sitemap")
            article["source_feed"] = None

            # Use the sitemap's last-modified date if the page lacks a date.
            if not article.get("published_at"):
                article["published_at"] = record.get("last_modified")

            was_inserted = save_article(article)

            if was_inserted:
                new_count += 1
                print(f"Saved new article: {article['title']}")
            else:
                duplicate_count += 1
                print(f"Already stored; refreshed check time: {article['title']}")

        except Exception as error:
            error_count += 1
            print(f"Could not process {page_url}: {error}")

    print("\nSitemap monitoring run completed.")
    print(f"Discovered URLs: {len(records)}")
    print(f"Pages processed: {len(records_to_process)}")
    print(f"New articles saved: {new_count}")
    print(f"Existing articles refreshed: {duplicate_count}")
    print(f"Errors: {error_count}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect and store article metadata from a website sitemap."
    )
    parser.add_argument(
        "website_url",
        help="Website homepage URL, for example https://blog.python.org"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of sitemap pages to parse (default: 10)"
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    initialize_database()
    monitor_sitemap(args.website_url, limit=args.limit)