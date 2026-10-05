import sqlite3

connection = sqlite3.connect("articles.db")
connection.row_factory = sqlite3.Row

rows = connection.execute("""
    SELECT
        title,
        url,
        source_name,
        source_type,
        source_sitemap,
        image_url
    FROM articles
    WHERE source_type = ?
    ORDER BY id DESC
    LIMIT 5
""", ("sitemap",)).fetchall()

for row in rows:
    print(dict(row))

count = connection.execute("""
    SELECT COUNT(*)
    FROM articles
    WHERE source_type = ?
""", ("sitemap",)).fetchone()[0]

print("\nSitemap records:", count)

connection.close()