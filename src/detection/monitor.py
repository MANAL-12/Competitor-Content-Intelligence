import json
import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dateutil import parser as date_parser


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from collectors.rss_collector import collect_rss_articles
from collectors.sitemap_collector import collect_sitemap_urls
from processing.article_parser import extract_article_details
from database.db import (
    initialize_database,
    save_article,
    record_monitoring_check,
    get_existing_article_urls
)


CONFIG_FILE = PROJECT_ROOT / "config" / "sites.json"
LOG_FILE = PROJECT_ROOT / "monitor.log"

# Check every 60 seconds
CHECK_INTERVAL_SECONDS = 60

# Only accept articles published/updated within the last 48 hours
RECENT_ARTICLE_HOURS = 48

# Maximum number of new sitemap articles processed per cycle
SITEMAP_LIMIT_DEFAULT = 5


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)


def load_sites():
    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        config = json.load(file)

    return [
        site
        for site in config.get("sites", [])
        if site.get("enabled", True)
    ]


def parse_datetime(value):
    """
    Convert a date string into a timezone-aware datetime.
    Supports ISO and common RSS date formats.
    """
    if not value:
        return None

    try:
        parsed = date_parser.parse(str(value))

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except (ValueError, TypeError, OverflowError):
        return None


def is_recent_article(published_at):
    """
    Return True if the article date is within the recent article window.
    """
    published = parse_datetime(published_at)

    if published is None:
        return False

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(hours=RECENT_ARTICLE_HOURS)
    )

    return published >= cutoff

def is_likely_blog_article(url):
    """
    Return True for URLs that are likely to be actual blog articles.
    Skip glossary, documentation, and reference pages.
    """
    url_lower = url.lower()

    excluded_paths = [
        "/glossary/",
        "/library/",
        "/reference/",
        "/tutorials/",
        "/courses/",
        "/learning-paths/",
        "/python-stdlib/",
    ]

    return not any(
        path in url_lower
        for path in excluded_paths
    )

def monitor_rss(site, feed_url):
    name = site["name"]

    logging.info(
        "RSS CHECK | %s | %s",
        name,
        feed_url
    )

    articles = collect_rss_articles(feed_url)

    new_count = 0
    duplicate_count = 0
    old_count = 0

    for article in articles:

        # Ignore old RSS entries
        if not is_recent_article(article.get("published_at")):
            old_count += 1
            continue

        article["source_name"] = name
        article["source_type"] = "rss"
        article["source_feed"] = feed_url
        article["detection_method"] = "RSS/Atom"
        article["first_detected_at"] = (
            datetime.now(timezone.utc).isoformat()
        )

        if save_article(article):
            new_count += 1
        else:
            duplicate_count += 1

    logging.info(
        "RSS COMPLETE | %s | retrieved=%d | recent=%d | old=%d | new=%d | duplicates=%d",
        name,
        len(articles),
        len(articles) - old_count,
        old_count,
        new_count,
        duplicate_count
    )

    return len(articles), new_count


def monitor_sitemap(site):
    name = site["name"]
    website_url = site["website_url"]

    logging.info(
        "SITEMAP CHECK | %s | %s",
        name,
        website_url
    )

    records = collect_sitemap_urls(website_url)

    existing_urls = get_existing_article_urls(
        [record["url"] for record in records]
    )

    new_records = [
        record
        for record in records
        if (
            record["url"] not in existing_urls
            and is_likely_blog_article(record["url"])
        )
    ]

    # Prioritize sitemap records with the newest lastmod date.
    # This prevents old sitemap entries from being processed first.
    def sitemap_date(record):
        parsed = parse_datetime(record.get("last_modified"))

        if parsed is None:
            return datetime.min.replace(tzinfo=timezone.utc)

        return parsed

    new_records.sort(
        key=sitemap_date,
        reverse=True
    )

    limit = site.get(
        "sitemap_limit",
        SITEMAP_LIMIT_DEFAULT
    )

    records_to_process = new_records[:limit]

    new_count = 0
    error_count = 0
    old_count = 0

    for record in records_to_process:

        page_url = record["url"]

        try:
            article = extract_article_details(page_url)

            if not article:
                continue

            # Prefer actual article publication date.
            published_at = article.get("published_at")

            # If the webpage doesn't provide a publication date,
            # use sitemap last-modified date.
            if not published_at:
                published_at = record.get("last_modified")

            # Ignore old sitemap articles.
            if not is_recent_article(published_at):
                old_count += 1
                continue

            article["published_at"] = published_at
            article["source_name"] = name
            article["source_type"] = "sitemap"
            article["source_sitemap"] = record.get(
                "source_sitemap"
            )
            article["source_feed"] = None
            article["detection_method"] = "XML Sitemap"
            article["first_detected_at"] = (
                datetime.now(timezone.utc).isoformat()
            )

            if save_article(article):
                new_count += 1

        except Exception:
            error_count += 1

            logging.exception(
                "SITEMAP PAGE FAILED | %s",
                page_url
            )

    logging.info(
        "SITEMAP COMPLETE | %s | discovered=%d | unseen=%d | processed=%d | recent=%d | old=%d | new=%d | errors=%d",
        name,
        len(records),
        len(new_records),
        len(records_to_process),
        new_count,
        old_count,
        new_count,
        error_count
    )

    return len(records), new_count


def monitor_direct(site):
    name = site["name"]
    website_url = site["website_url"]

    logging.info(
        "DIRECT PAGE CHECK | %s | %s",
        name,
        website_url
    )

    article = extract_article_details(website_url)

    if not article:
        logging.info(
            "DIRECT PAGE | %s | no article metadata detected",
            name
        )
        return 0, 0

    # Do not store an old article from the direct page.
    if not is_recent_article(article.get("published_at")):
        logging.info(
            "DIRECT PAGE | %s | article is older than %d hours",
            name,
            RECENT_ARTICLE_HOURS
        )
        return 1, 0

    article["source_name"] = name
    article["source_type"] = "direct"
    article["detection_method"] = "Direct Page"
    article["first_detected_at"] = (
        datetime.now(timezone.utc).isoformat()
    )

    inserted = save_article(article)

    return 1, 1 if inserted else 0


def monitor_site(site):

    name = site["name"]
    website_url = site["website_url"]

    cycle_start = datetime.now(timezone.utc).isoformat()

    total_found = 0
    total_new = 0

    try:

        logging.info(
            "START COMPETITOR CHECK | %s",
            name
        )

        sources = site.get("sources", {})

        # -------------------------
        # RSS
        # -------------------------
        for feed_url in sources.get("rss", []):

            found, new = monitor_rss(
                site,
                feed_url
            )

            total_found += found
            total_new += new

        # -------------------------
        # Sitemap
        # -------------------------
        if sources.get("sitemap", False):

            found, new = monitor_sitemap(site)

            total_found += found
            total_new += new

        # -------------------------
        # Direct page
        # -------------------------
        if sources.get("direct", False):

            found, new = monitor_direct(site)

            total_found += found
            total_new += new

        finished = datetime.now(timezone.utc).isoformat()

        record_monitoring_check(
            competitor=name,
            website_url=website_url,
            started_at=cycle_start,
            finished_at=finished,
            status="SUCCESS",
            articles_found=total_found,
            new_articles=total_new
        )

        logging.info(
            "COMPETITOR CHECK COMPLETE | %s | found=%d | new=%d",
            name,
            total_found,
            total_new
        )

    except Exception as error:

        finished = datetime.now(timezone.utc).isoformat()

        record_monitoring_check(
            competitor=name,
            website_url=website_url,
            started_at=cycle_start,
            finished_at=finished,
            status="FAILED",
            articles_found=total_found,
            new_articles=total_new,
            error_message=str(error)
        )

        logging.exception(
            "COMPETITOR FAILED | %s",
            name
        )


def run_monitor():

    initialize_database()

    logging.info(
        "Competitor monitoring system started."
    )

    logging.info(
        "Recent article window: last %d hours",
        RECENT_ARTICLE_HOURS
    )

    while True:

        cycle_start = time.time()

        try:

            sites = load_sites()

            logging.info(
                "MONITORING CYCLE START | competitors=%d",
                len(sites)
            )

            for site in sites:
                monitor_site(site)

            elapsed = time.time() - cycle_start

            logging.info(
                "MONITORING CYCLE COMPLETE | competitors=%d | elapsed=%.2f seconds",
                len(sites),
                elapsed
            )

        except Exception:
            logging.exception(
                "MONITORING CYCLE ERROR"
            )

        elapsed = time.time() - cycle_start

        sleep_time = max(
            1,
            CHECK_INTERVAL_SECONDS - int(elapsed)
        )

        time.sleep(sleep_time)


if __name__ == "__main__":
    run_monitor()