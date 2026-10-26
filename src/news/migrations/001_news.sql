-- Retain observations and decisions separately so later editorial profiles do not rewrite history.
CREATE TABLE schema_versions (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE sources (name text PRIMARY KEY, category text NOT NULL, feed_url text);
CREATE TABLE articles (
    id text PRIMARY KEY, canonical_url text NOT NULL UNIQUE,
    first_seen_at timestamptz NOT NULL DEFAULT now(), last_seen_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE runs (
    id uuid PRIMARY KEY, started_at timestamptz NOT NULL, finished_at timestamptz,
    status text NOT NULL CHECK (status IN ('running','failed','ready_for_review')),
    stage text NOT NULL, config jsonb NOT NULL, error_type text
);
CREATE TABLE observations (
    run_id uuid NOT NULL REFERENCES runs(id), ordinal integer NOT NULL,
    article_id text NOT NULL REFERENCES articles(id), source_name text NOT NULL REFERENCES sources(name),
    published_at timestamptz, date_basis text NOT NULL, title text NOT NULL,
    eligibility text, metadata jsonb NOT NULL, PRIMARY KEY(run_id,ordinal)
);
CREATE INDEX observations_article ON observations(article_id);
CREATE INDEX observations_source_date ON observations(source_name,published_at);
CREATE TABLE stages (
    run_id uuid NOT NULL REFERENCES runs(id), name text NOT NULL, item_key text NOT NULL DEFAULT '',
    status text NOT NULL CHECK(status IN ('running','failed','complete')),
    attempts integer NOT NULL DEFAULT 1, started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz, output jsonb, error_type text, PRIMARY KEY(run_id,name,item_key)
);
CREATE TABLE events (
    run_id uuid NOT NULL REFERENCES runs(id), event_id text NOT NULL,
    title text NOT NULL, novelty text NOT NULL CHECK(novelty IN ('new','repeat','update')),
    payload jsonb NOT NULL, PRIMARY KEY(run_id,event_id)
);
CREATE TABLE event_articles (
    run_id uuid NOT NULL, event_id text NOT NULL, article_id text NOT NULL REFERENCES articles(id),
    PRIMARY KEY(run_id,event_id,article_id),
    FOREIGN KEY(run_id,event_id) REFERENCES events(run_id,event_id)
);
CREATE TABLE decisions (
    run_id uuid NOT NULL, event_id text NOT NULL, phase text NOT NULL,
    profile_id text NOT NULL, profile_version integer NOT NULL,
    tag text, tier text, score double precision, reason text NOT NULL, basis text, payload jsonb NOT NULL,
    PRIMARY KEY(run_id,event_id,phase), FOREIGN KEY(run_id,event_id) REFERENCES events(run_id,event_id)
);
CREATE INDEX decisions_profile ON decisions(profile_id,profile_version,phase);
CREATE TABLE evidence (
    run_id uuid NOT NULL REFERENCES runs(id), article_id text NOT NULL REFERENCES articles(id),
    basis text NOT NULL, status text NOT NULL, content_sha256 text NOT NULL,
    retrieved_at timestamptz NOT NULL DEFAULT now(), payload jsonb NOT NULL,
    PRIMARY KEY(run_id,article_id)
);
CREATE TABLE model_calls (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, run_id uuid NOT NULL REFERENCES runs(id),
    task text NOT NULL, prompt_sha256 text NOT NULL, request jsonb NOT NULL, response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE editions (
    run_id uuid PRIMARY KEY REFERENCES runs(id), profile_id text NOT NULL,
    status text NOT NULL CHECK(status IN ('ready_for_review','published')),
    published_at timestamptz, payload jsonb NOT NULL
);
CREATE TABLE storage_samples (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, sampled_at timestamptz NOT NULL DEFAULT now(),
    database_bytes bigint NOT NULL, tables_bytes bigint NOT NULL, row_counts jsonb NOT NULL
);
INSERT INTO schema_versions(version) VALUES(1);
