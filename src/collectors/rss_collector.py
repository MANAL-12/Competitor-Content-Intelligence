
import requests
import feedparser
from datetime import datetime, timezone


def collect_rss_articles(feed_url):
    """
    Download an RSS/Atom feed securely with requests,
    parse it with feedparser, and return article metadata.
    """
    headers = {
        "User-Agent": "CompetitorContentMonitor/1.0"
    }

    response = requests.get(
        feed_url,
        headers=headers,
        timeout=20
    )
    response.raise_for_status()

    # Parse the downloaded content instead of asking
    # feedparser to make its own network request.
    feed = feedparser.parse(response.content)

    if feed.bozo:
        raise ValueError(
            f"Could not parse the feed: {feed.bozo_exception}"
        )

    articles = []

    for entry in feed.entries:
        published_at = None

        if entry.get("published_parsed"):
            published_at = datetime(
                *entry.published_parsed[:6],
                tzinfo=timezone.utc
            ).isoformat()
        elif entry.get("updated_parsed"):
            published_at = datetime(
                *entry.updated_parsed[:6],
                tzinfo=timezone.utc
            ).isoformat()

        author = entry.get("author")
        if isinstance(author, dict):
            author = author.get("name")

        article = {
            "title": entry.get("title", "Untitled"),
            "url": entry.get("link"),
            "published_at": published_at,
            "summary": entry.get("summary", ""),
            "author": author,
            "source_feed": feed_url
        }

        # Skip entries without a usable URL, since the
        # database uses the URL to identify duplicates.
        if article["url"]:
            articles.append(article)

    return articles


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python src/collectors/rss_collector.py "
            "<feed_url>"
        )
        sys.exit(1)

    url = sys.argv[1]

    try:
        articles = collect_rss_articles(url)
        print(f"Retrieved {len(articles)} articles.")

        for index, article in enumerate(articles, start=1):
            print(f"\n{index}. {article['title']}")
            print(f"   URL: {article['url']}")
            print(f"   Published: {article['published_at']}")

    except Exception as error:
        print(f"Feed collection failed: {error}")
        sys.exit(1)