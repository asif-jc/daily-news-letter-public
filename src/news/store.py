"""
=== store.py ===

Purpose: Retain queryable news data and transactional run checkpoints.
Extended Description:
    Database queries only; workflow orchestration belongs in workflow.py.
Usage:
    Use NewsStore.from_env(); call migrate() before operations.
Work Log:
    19/10/2026 -> PostgreSQL-backed news-only MVP.
"""

# ========================================================================
# IMPORTS & CONFIGURATION
# ========================================================================
import hashlib
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.mvp_news_aggregator.sources import RSS_FEEDS
from .events import canonical_url

TABLES = (
    "sources",
    "articles",
    "observations",
    "runs",
    "stages",
    "events",
    "event_articles",
    "decisions",
    "evidence",
    "model_calls",
    "editions",
    "article_analyses",
)


def _edition_generated_at(row):
    # Legacy editions may lack a usable generation date; the owning run supplies its boundary.
    try:
        generated = datetime.fromisoformat(row["payload"].get("generated_at") or "")
        return generated if generated.tzinfo else generated.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return row["started_at"]


# ========================================================================
# NEWS STORAGE
# ========================================================================


class NewsStore:
    def __init__(self, dsn, schema="news"):
        if conninfo_to_dict(dsn).get("dbname") != "news":
            raise ValueError("The news workflow only writes to the news database")
        if schema != "news" and not re.fullmatch(r"test_[a-z0-9_]+", schema):
            raise ValueError("Use the news schema or an isolated test schema")
        self.schema = schema
        self.connection = psycopg.connect(
            dsn,
            autocommit=True,
            row_factory=dict_row,
            connect_timeout=8,
            application_name="news-mvp",
        )
        if (
            self.connection.execute("SELECT current_database() AS name").fetchone()[
                "name"
            ]
            != "news"
        ):
            self.connection.close()
            raise ValueError("Connected database is not news")
        self.connection.execute(
            sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema))
        )

    @classmethod
    def from_env(cls):
        dsn = os.getenv("NEWS_DATABASE_URL")
        if not dsn:
            raise ValueError("Set NEWS_DATABASE_URL in an ignored environment file")
        return cls(dsn)

    def close(self):
        self.connection.close()

    def transaction(self):
        return self.connection.transaction()

    def migrate(self):
        with self.transaction():
            self.connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("news-migrations:" + self.schema,),
            )
            self.connection.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                    sql.Identifier(self.schema)
                )
            )
            exists = self.connection.execute(
                "SELECT to_regclass(%s) AS name", (self.schema + ".schema_versions",)
            ).fetchone()["name"]
            if not exists:
                self.connection.execute(
                    (Path(__file__).parent / "migrations/001_news.sql").read_text()
                )
            version = self.connection.execute(
                "SELECT max(version) AS version FROM schema_versions"
            ).fetchone()["version"]
            if version not in (1, 2):
                raise ValueError("Unsupported news schema version")
            if version == 1:
                self.connection.execute(
                    (Path(__file__).parent / "migrations/002_library.sql").read_text()
                )

    def create_run(self, config, now):
        id = str(uuid.uuid4())
        self.connection.execute(
            "INSERT INTO runs(id,started_at,status,stage,config) VALUES(%s,%s,'running','collect',%s)",
            (id, now, Jsonb(config)),
        )
        return id

    def get_run(self, run_id):
        row = self.connection.execute(
            "SELECT * FROM runs WHERE id=%s", (run_id,)
        ).fetchone()
        if not row:
            raise ValueError("Unknown run ID")
        return row

    @contextmanager
    def lock_run(self, run_id):
        key = self.schema + ":" + str(run_id)
        locked = self.connection.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS ok", (key,)
        ).fetchone()["ok"]
        if not locked:
            raise RuntimeError("Run is already executing on another connection")
        try:
            yield
        finally:
            self.connection.execute(
                "SELECT pg_advisory_unlock(hashtextextended(%s,0))", (key,)
            )

    def stage_output(self, run_id, name, item_key=""):
        row = self.connection.execute(
            "SELECT output FROM stages WHERE run_id=%s AND name=%s AND item_key=%s AND status='complete'",
            (run_id, name, item_key),
        ).fetchone()
        return row["output"] if row else None

    def start_stage(self, run_id, name, item_key=""):
        with self.transaction():
            self.connection.execute(
                "UPDATE runs SET status='running',stage=%s,error_type=NULL WHERE id=%s",
                (name, run_id),
            )
            self.connection.execute(
                """INSERT INTO stages(run_id,name,item_key,status) VALUES(%s,%s,%s,'running')
                ON CONFLICT(run_id,name,item_key) DO UPDATE SET status='running',attempts=stages.attempts+1,
                started_at=now(),finished_at=NULL,error_type=NULL WHERE stages.status!='complete'""",
                (run_id, name, item_key),
            )

    def complete_stage(self, run_id, name, output, item_key=""):
        row = self.connection.execute(
            """UPDATE stages SET status='complete',output=%s,finished_at=now()
            WHERE run_id=%s AND name=%s AND item_key=%s AND status!='complete' RETURNING name""",
            (Jsonb(output), run_id, name, item_key),
        ).fetchone()
        if not row:
            raise ValueError("Stage is absent or already complete")

    def fail_stage(self, run_id, name, error, item_key=""):
        with self.transaction():
            self.connection.execute(
                "UPDATE stages SET status='failed',error_type=%s,output=%s,finished_at=now() WHERE run_id=%s AND name=%s AND item_key=%s AND status!='complete'",
                (
                    type(error).__name__,
                    Jsonb({"error_message": str(error)[:500]}),
                    run_id,
                    name,
                    item_key,
                ),
            )
            self.connection.execute(
                "UPDATE runs SET status='failed',stage=%s,error_type=%s WHERE id=%s",
                (name, type(error).__name__, run_id),
            )

    def save_articles(self, run_id, articles):
        with self.transaction():
            for n, article in enumerate(articles):
                feed_url = next(
                    (
                        f["url"]
                        for feeds in RSS_FEEDS.values()
                        for f in feeds
                        if f["name"] == article["source"]
                    ),
                    None,
                )
                self.connection.execute(
                    "INSERT INTO sources(name,category,feed_url) VALUES(%s,%s,%s) ON CONFLICT(name) DO NOTHING",
                    (article["source"], article["category"], feed_url),
                )
                try:
                    url = canonical_url(article["url"])
                except (ValueError, TypeError):
                    # Invalid observations still need an identity and must remain inspectable.
                    url = "invalid:" + article["id"]
                self.connection.execute(
                    "INSERT INTO articles(id,canonical_url) VALUES(%s,%s) ON CONFLICT(id) DO UPDATE SET last_seen_at=now()",
                    (article["id"], url),
                )
                self.connection.execute(
                    """INSERT INTO observations(run_id,ordinal,article_id,source_name,published_at,date_basis,title,metadata)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(run_id,ordinal) DO NOTHING""",
                    (
                        run_id,
                        n,
                        article["id"],
                        article["source"],
                        article.get("published"),
                        article.get("published_basis", "unknown"),
                        article["title"],
                        Jsonb(article),
                    ),
                )

    def observations(self, run_id):
        return [
            r["metadata"]
            for r in self.connection.execute(
                "SELECT metadata FROM observations WHERE run_id=%s ORDER BY ordinal",
                (run_id,),
            )
        ]

    def rolling_articles(self, now, days=7):
        """Use publisher dates for freshness, or last observation when both are unknown."""
        if days <= 0:
            raise ValueError("Rolling window days must be positive")
        cutoff = now - timedelta(days=days)
        rows = self.connection.execute(
            """SELECT DISTINCT ON (o.article_id) o.metadata,r.started_at AS observed_at
            FROM observations o JOIN runs r ON r.id=o.run_id
            WHERE r.started_at <= %s
            ORDER BY o.article_id,r.started_at DESC,r.id DESC,o.ordinal DESC""",
            (now,),
        )
        articles = []
        for row in rows:
            article = row["metadata"]
            dates = []
            for field in ("published", "updated"):
                try:
                    value = datetime.fromisoformat(article.get(field) or "")
                except (ValueError, TypeError):
                    continue
                dates.append(
                    value if value.tzinfo else value.replace(tzinfo=timezone.utc)
                )
            if (not dates and row["observed_at"] >= cutoff) or any(
                cutoff <= date <= now for date in dates
            ):
                articles.append(article)
        return articles

    def cached_analysis(self, article_id, input_key, since):
        """Return the newest exact-key payload created at or after since."""
        row = self.connection.execute(
            """SELECT payload FROM article_analyses
            WHERE article_id=%s AND input_key=%s AND created_at >= %s
            ORDER BY created_at DESC,id DESC LIMIT 1""",
            (article_id, input_key, since),
        ).fetchone()
        return row["payload"] if row else None

    def save_analysis(self, article_id, input_key, payload):
        self.connection.execute(
            "INSERT INTO article_analyses(article_id,input_key,payload) VALUES(%s,%s,%s)",
            (article_id, input_key, Jsonb(payload)),
        )

    def save_filter(self, run_id, candidates, exclusions):
        with self.transaction():
            self.connection.execute(
                "UPDATE observations SET eligibility='eligible' WHERE run_id=%s",
                (run_id,),
            )
            for exclusion in exclusions:
                self.connection.execute(
                    "UPDATE observations SET eligibility=%s WHERE run_id=%s AND ordinal=%s",
                    (exclusion["reason"], run_id, exclusion["ordinal"]),
                )

    def save_events(self, run_id, events):
        with self.transaction():
            for event in events:
                self.connection.execute(
                    "INSERT INTO events(run_id,event_id,title,novelty,payload) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (
                        run_id,
                        event["event_id"],
                        event["title"],
                        event["novelty"],
                        Jsonb(event),
                    ),
                )
                for id in event["source_ids"]:
                    self.connection.execute(
                        "INSERT INTO event_articles VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                        (run_id, event["event_id"], id),
                    )

    def save_decisions(self, run_id, phase, decisions, profile):
        with self.transaction():
            for d in decisions:
                self.connection.execute(
                    """INSERT INTO decisions(run_id,event_id,phase,profile_id,profile_version,tag,tier,score,reason,basis,payload)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                    (
                        run_id,
                        d["event_id"],
                        phase,
                        profile["id"],
                        profile["version"],
                        d.get("tag"),
                        d.get("tier"),
                        d.get("score"),
                        d["reason"],
                        d.get("decision_basis"),
                        Jsonb(d),
                    ),
                )

    def save_evidence(self, run_id, article_id, evidence):
        self.connection.execute(
            """INSERT INTO evidence(run_id,article_id,basis,status,content_sha256,payload)
            VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (
                run_id,
                article_id,
                evidence["basis"],
                evidence["status"],
                hashlib.sha256(evidence["text"].encode()).hexdigest(),
                Jsonb(evidence),
            ),
        )

    def audit_model(self, run_id, task, messages, response):
        prompt_hash = hashlib.sha256(messages[0]["content"].encode()).hexdigest()
        self.connection.execute(
            "INSERT INTO model_calls(run_id,task,prompt_sha256,request,response) VALUES(%s,%s,%s,%s,%s)",
            (run_id, task, prompt_hash, Jsonb(messages), Jsonb(response)),
        )

    def save_edition(self, run_id, edition, profile):
        self.connection.execute(
            "INSERT INTO editions(run_id,profile_id,status,payload) VALUES(%s,%s,'ready_for_review',%s) ON CONFLICT DO NOTHING",
            (run_id, profile["id"], Jsonb(edition)),
        )

    def recent_editions(self, profile_id, limit=7, now=None):
        """Return snapshots with publication state; preview history never implies publication."""
        if limit < 0:
            raise ValueError("Edition limit must not be negative")
        rows = self.connection.execute(
            """SELECT e.run_id,e.status,e.published_at,e.payload,r.started_at
            FROM editions e JOIN runs r ON r.id=e.run_id
            WHERE e.profile_id=%s AND (%s::timestamptz IS NULL OR r.started_at <= %s)
            ORDER BY r.started_at DESC,e.run_id DESC""",
            (profile_id, now, now),
        )
        editions = []
        for row in rows:
            generated = _edition_generated_at(row)
            if now is None or generated <= now:
                editions.append(
                    (
                        generated,
                        {
                            **row["payload"],
                            "run_id": str(row["run_id"]),
                            "publication_status": row["status"],
                            "published_at": (
                                row["published_at"].isoformat()
                                if row["published_at"]
                                else None
                            ),
                        },
                    )
                )
        editions.sort(key=lambda item: item[0], reverse=True)
        return [edition for _, edition in editions[:limit]]

    def published_history(self, profile_id, now=None, days=7):
        rows = self.connection.execute(
            """SELECT e.payload,r.started_at FROM editions e JOIN runs r ON r.id=e.run_id
            WHERE e.profile_id=%s AND e.status='published'
            AND (%s::timestamptz IS NULL OR (r.started_at <= %s AND e.published_at <= %s AND e.published_at >= %s))
            ORDER BY e.published_at DESC LIMIT %s""",
            (
                profile_id,
                now,
                now,
                now,
                now - timedelta(days=days) if now else None,
                7 if now is None else None,
            ),
        )
        stories, featured_ids = {}, set()
        for row in rows:
            if now is not None and _edition_generated_at(row) > now:
                continue
            for story in row["payload"]["stories"]:
                if story.get("featured", True):
                    featured_ids.add(story["event_id"])
                stories.setdefault(story["event_id"], story)
        # Latest factual snapshots and past placement answer different questions.
        return {
            "stories": list(stories.values()),
            "featured_event_ids": sorted(featured_ids),
        }

    def finish_run(self, run_id):
        self.connection.execute(
            "UPDATE runs SET status='ready_for_review',stage='complete',finished_at=coalesce(finished_at,now()) WHERE id=%s",
            (run_id,),
        )

    def counts(self):
        return {
            table: self.connection.execute(
                sql.SQL("SELECT count(*) AS n FROM {}").format(sql.Identifier(table))
            ).fetchone()["n"]
            for table in TABLES
        }

    def stats(self):
        counts = self.counts()
        database_bytes = self.connection.execute(
            "SELECT pg_database_size(current_database()) AS n"
        ).fetchone()["n"]
        tables_bytes = self.connection.execute(
            "SELECT coalesce(sum(pg_total_relation_size(c.oid)),0)::bigint AS n FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind=%s",
            (self.schema, "r"),
        ).fetchone()["n"]
        self.connection.execute(
            "INSERT INTO storage_samples(database_bytes,tables_bytes,row_counts) VALUES(%s,%s,%s)",
            (database_bytes, tables_bytes, Jsonb(counts)),
        )
        return {
            "database_bytes": database_bytes,
            "tables_bytes": tables_bytes,
            "rows": counts,
        }
