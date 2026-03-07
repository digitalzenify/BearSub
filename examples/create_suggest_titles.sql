-- SubsDump helper table for very fast IMDb/title suggestions
-- This table is optional for the original dump, but required by the current
-- _imdb_suggest_impl implementation used by SubsDump frontend suggestions.

USE subscene_db;

DROP TABLE IF EXISTS suggest_titles;

CREATE TABLE suggest_titles (
  imdb INT(10) UNSIGNED NOT NULL,
  title VARCHAR(255) NOT NULL,
  cnt INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (imdb),
  KEY idx_title (title),
  KEY idx_cnt (cnt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO suggest_titles (imdb, title, cnt)
SELECT
  imdb,
  MAX(title) AS title,
  COUNT(*) AS cnt
FROM all_subs
WHERE title IS NOT NULL
  AND title <> ''
  AND imdb IS NOT NULL
  AND imdb <> 0
GROUP BY imdb;

-- Optional:
-- If your read-only API user does not already have SELECT on subscene_db.*,
-- grant access only to this helper table as well.
--
-- GRANT SELECT ON subscene_db.suggest_titles TO 'subscene_ro'@'%';
-- FLUSH PRIVILEGES;
