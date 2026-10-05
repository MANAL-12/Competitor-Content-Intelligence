import sqlite3

c = sqlite3.connect("articles.db")

rows = c.execute("""
SELECT
    title,
    source_name,
    published_at,
    first_detected_at,
    detection_delay_seconds,
    detection_method
FROM articles
WHERE published_at IS NOT NULL
  AND detection_method = 'RSS/Atom'
ORDER BY id DESC
LIMIT 10
""").fetchall()

for row in rows:
    print(row)

c.close()