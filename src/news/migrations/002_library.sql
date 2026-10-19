-- Retain analyses independently of runs so unchanged metadata can reuse reviewed evidence.
CREATE TABLE article_analyses (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    article_id text NOT NULL REFERENCES articles(id), input_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(), payload jsonb NOT NULL
);
CREATE INDEX article_analyses_cache ON article_analyses(article_id,input_key,created_at DESC,id DESC);
CREATE INDEX editions_profile ON editions(profile_id);
INSERT INTO schema_versions(version) VALUES(2);
