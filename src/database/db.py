import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "articles.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():

    with get_connection() as connection:

        # Articles table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                url TEXT UNIQUE,
                published_at TEXT,
                summary TEXT,
                author TEXT,
                source_feed TEXT,
                first_detected_at TEXT,
                last_checked_at TEXT,
                source_name TEXT,
                image_url TEXT,
                source_type TEXT,
                source_sitemap TEXT,
                detection_delay_seconds REAL,
                detection_method TEXT
            )
        """)

        # Add columns if an older database is being used
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(articles)"
            ).fetchall()
        }

        new_columns = {
            "detection_delay_seconds": "REAL",
            "detection_method": "TEXT"
        }

        for column, data_type in new_columns.items():

            if column not in columns:

                connection.execute(
                    f"ALTER TABLE articles ADD COLUMN {column} {data_type}"
                )

        # Monitoring history table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor TEXT NOT NULL,
                website_url TEXT,
                started_at TEXT,
                finished_at TEXT,
                status TEXT,
                articles_found INTEGER DEFAULT 0,
                new_articles INTEGER DEFAULT 0,
                error_message TEXT
            )
        """)

        connection.commit()


def save_article(article):

    initialize_database()

    now = datetime.now(timezone.utc).isoformat()

    published_at = article.get("published_at")

    detected_at = (
        article.get("first_detected_at")
        or now
    )

    detection_delay = article.get(
        "detection_delay_seconds"
    )

    # Calculate detection delay
    if detection_delay is None and published_at and detected_at:

        try:

            published = datetime.fromisoformat(
                published_at.replace("Z", "+00:00")
            )

            detected = datetime.fromisoformat(
                detected_at.replace("Z", "+00:00")
            )

            detection_delay = max(
                0,
                (detected - published).total_seconds()
            )

        except (ValueError, TypeError):

            detection_delay = None

    with get_connection() as connection:

        cursor = connection.execute("""
            INSERT OR IGNORE INTO articles (
                title,
                url,
                published_at,
                summary,
                author,
                source_feed,
                first_detected_at,
                last_checked_at,
                source_name,
                image_url,
                source_type,
                source_sitemap,
                detection_delay_seconds,
                detection_method
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            article.get("title"),
            article.get("url"),
            published_at,
            article.get("summary"),
            article.get("author"),
            article.get("source_feed"),
            detected_at,
            now,
            article.get("source_name"),
            article.get("image_url"),
            article.get("source_type"),
            article.get("source_sitemap"),
            detection_delay,
            article.get("detection_method")
        ))

        inserted = cursor.rowcount > 0

        # Update existing article
        if not inserted:

            connection.execute("""
                UPDATE articles
                SET
                    last_checked_at = ?,
                    summary = COALESCE(summary, ?),
                    author = COALESCE(author, ?),
                    image_url = COALESCE(image_url, ?),
                    published_at = COALESCE(published_at, ?),
                    detection_delay_seconds =
                        COALESCE(
                            detection_delay_seconds,
                            ?
                        ),
                    detection_method =
                        COALESCE(
                            detection_method,
                            ?
                        )
                WHERE url = ?
            """, (

                now,
                article.get("summary"),
                article.get("author"),
                article.get("image_url"),
                published_at,
                detection_delay,
                article.get("detection_method"),
                article.get("url")
            ))

        connection.commit()

    return inserted


def article_exists(url):

    with get_connection() as connection:

        row = connection.execute(
            """
            SELECT 1
            FROM articles
            WHERE url = ?
            LIMIT 1
            """,
            (url,)
        ).fetchone()

    return row is not None

def get_existing_article_urls(urls):

    initialize_database()

    if not urls:
        return set()

    existing = set()

    with get_connection() as connection:

        for url in urls:

            row = connection.execute(
                """
                SELECT 1
                FROM articles
                WHERE url = ?
                LIMIT 1
                """,
                (url,)
            ).fetchone()

            if row:
                existing.add(url)

    return existing

def record_monitoring_check(
    competitor,
    website_url,
    started_at,
    finished_at,
    status,
    articles_found=0,
    new_articles=0,
    error_message=None
):

    initialize_database()

    with get_connection() as connection:

        connection.execute("""
            INSERT INTO monitoring_checks (
                competitor,
                website_url,
                started_at,
                finished_at,
                status,
                articles_found,
                new_articles,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (

            competitor,
            website_url,
            started_at,
            finished_at,
            status,
            articles_found,
            new_articles,
            error_message
        ))

        connection.commit()


def get_monitoring_status():

    initialize_database()

    with get_connection() as connection:

        rows = connection.execute("""
            SELECT
                competitor,
                website_url,
                MAX(finished_at) AS last_checked,
                MAX(
                    CASE
                        WHEN status = 'SUCCESS'
                        THEN finished_at
                    END
                ) AS last_success,
                SUM(
                    CASE
                        WHEN status = 'FAILED'
                        THEN 1
                        ELSE 0
                    END
                ) AS failed_checks,
                COUNT(*) AS total_checks
            FROM monitoring_checks
            GROUP BY competitor, website_url
            ORDER BY competitor
        """).fetchall()

    return rows


def get_all_articles():

    initialize_database()

    with get_connection() as connection:

        cursor = connection.execute("""
            SELECT *
            FROM articles
            ORDER BY first_detected_at DESC
        """)

        rows = cursor.fetchall()

        columns = [
            description[0]
            for description in cursor.description
        ]

    return [
        dict(zip(columns, row))
        for row in rows
    ]


if __name__ == "__main__":

    initialize_database()

    with get_connection() as connection:

        article_count = connection.execute(
            "SELECT COUNT(*) FROM articles"
        ).fetchone()[0]

        check_count = connection.execute(
            "SELECT COUNT(*) FROM monitoring_checks"
        ).fetchone()[0]

    print("Database initialized.")
    print("Stored articles:", article_count)
    print("Monitoring checks:", check_count)