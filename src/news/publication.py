"""Export reader-only releases and record publication after verified HTTP delivery.
Private run diagnostics stay in PostgreSQL and the review directory; this module never deploys.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import requests

from .ingest import write_json
from .render import reader_snapshot, render_edition, safe_link

MAX_PUBLIC_FILE_BYTES = 16 * 1024 * 1024
PRIVATE_TEXT = re.compile(
    r"\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|"
    r"100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+)\b|"
    r"[\w.-]+\.ts\.net\b|/(?:Users|home)/|\.local/",
    re.I,
)
ARCHIVE_PATH = re.compile(r"archive/([a-f0-9-]{36})\.html\Z")


# ========================================================================
# READER AND ARTIFACT BOUNDARIES
# ========================================================================


def public_snapshot(edition):
    if not edition.get("stories"):
        raise ValueError("An empty edition cannot be published")
    for story in edition["stories"]:
        if not story.get("summary", "").strip() or not story.get("sources"):
            raise ValueError("Every public story needs a summary and source links")
        if any(not safe_link(source.get("url", "")) for source in story["sources"]):
            raise ValueError("Unapproved source link in public edition")
    snapshot = reader_snapshot(edition)
    if PRIVATE_TEXT.search(json.dumps(snapshot, ensure_ascii=False)):
        raise ValueError("Private network or filesystem information in reader fields")
    return {**snapshot, "publication_status": "published"}


def artifact_path(path):
    if not isinstance(path, str):
        return False
    if path in ("index.html", "assets/dunder_park.jpg"):
        return True
    match = ARCHIVE_PATH.fullmatch(path)
    if match:
        try:
            return str(UUID(match[1])) == match[1]
        except ValueError:
            pass
    return False


def validate_manifest(manifest, run_id=None):
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("Unsupported public release manifest")
    if set(manifest) != {
        "schema_version",
        "run_id",
        "generated_at",
        "stories",
        "files",
    }:
        raise ValueError("Unexpected fields in public release manifest")
    try:
        UUID(manifest["run_id"])
        generated = datetime.fromisoformat(
            manifest["generated_at"].replace("Z", "+00:00")
        )
        if (
            generated.tzinfo is None
            or type(manifest["stories"]) is not int
            or manifest["stories"] < 1
        ):
            raise ValueError("Invalid public release metadata")
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid public release metadata") from None
    if run_id is not None and manifest.get("run_id") != run_id:
        raise ValueError("Release belongs to a different run")
    files = manifest.get("files")
    if (
        not isinstance(files, dict)
        or "index.html" not in files
        or "assets/dunder_park.jpg" not in files
        or any(
            not artifact_path(p)
            or not isinstance(d, str)
            or not re.fullmatch(r"[a-f0-9]{64}", d)
            for p, d in files.items()
        )
    ):
        raise ValueError("Unexpected release artifact or digest")
    return manifest


def verify_release_directory(output, run_id=None):
    """The deploy gate enforces the same reader-only contract as local export."""
    output = Path(output)
    entries = [output, *output.rglob("*")]
    if any(path.is_symlink() for path in entries):
        raise ValueError("Symlink in public release")
    manifest = validate_manifest(
        json.loads((output / "release.json").read_text()), run_id
    )
    actual = {p.relative_to(output).as_posix() for p in entries[1:] if p.is_file()}
    if actual != set(manifest["files"]) | {"release.json"}:
        raise ValueError("Unexpected files in public release")
    for path, digest in manifest["files"].items():
        data = (output / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Public release artifact hash mismatch")
        if path.endswith(".html") and PRIVATE_TEXT.search(data.decode()):
            raise ValueError("Private network or filesystem information in public page")
    return manifest


def release_files(store, run_id):
    edition, run = store.get_edition(run_id), store.get_run(run_id)
    if run["status"] != "ready_for_review":
        raise ValueError("Only a completed run can be exported")
    snapshot = public_snapshot(edition)
    archives = [
        public_snapshot(old)
        for old in run["config"].get("archives", [])
        if old.get("publication_status") == "published"
    ]
    files = {
        "index.html": render_edition(snapshot, archives).encode(),
        "assets/dunder_park.jpg": (
            Path(__file__).parent / "assets/dunder_park.jpg"
        ).read_bytes(),
    }
    for old in archives:
        path = "archive/" + old["run_id"] + ".html"
        if not artifact_path(path):
            raise ValueError("Invalid archive identity")
        html = render_edition(
            old, [a for a in archives if a["run_id"] != old["run_id"]]
        )
        files[path] = html.replace("<head>", '<head><base href="../">', 1).encode()
    return snapshot, files


def export_publication(store, run_id, output):
    snapshot, files = release_files(store, run_id)
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "generated_at": snapshot["generated_at"],
        "stories": len(snapshot["stories"]),
        "files": {
            path: hashlib.sha256(data).hexdigest() for path, data in files.items()
        },
    }
    validate_manifest(manifest, run_id)
    output = Path(output)
    old_files = set()
    if output.is_symlink():
        raise ValueError("Release output must not be a symlink")
    if output.exists():
        entries = list(output.rglob("*"))
        if any(p.is_symlink() for p in entries):
            raise ValueError("Release output contains a symlink")
        actual = {p.relative_to(output).as_posix() for p in entries if p.is_file()}
        if actual:
            if "release.json" not in actual:
                raise ValueError("Nonempty output is not a managed public release")
            old = validate_manifest(json.loads((output / "release.json").read_text()))
            old_files = set(old["files"])
            if actual != old_files | {"release.json"}:
                raise ValueError("Unexpected files in public release output")
    output.mkdir(parents=True, exist_ok=True)
    for path, data in files.items():
        destination = output / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(destination)
    for path in old_files - files.keys():
        (output / path).unlink()
    # Write the manifest last so it never certifies an incomplete export.
    write_json(output / "release.json", manifest)
    return manifest


# ========================================================================
# VERIFIED DELIVERY
# ========================================================================


def fetch_public_file(url):
    response = requests.get(
        url,
        timeout=(5, 30),
        stream=True,
        allow_redirects=False,
        headers={"Cache-Control": "no-cache"},
    )
    try:
        if response.is_redirect:
            raise ValueError("Unexpected redirect during public delivery verification")
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_PUBLIC_FILE_BYTES:
                raise ValueError("Public release file exceeds verification limit")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        response.close()


def confirm_publication(store, run_id, manifest_path, site_url):
    parsed = urlsplit(site_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.port not in (None, 443)
        or not parsed.hostname.endswith(".github.io")
    ):
        raise ValueError("Use the public HTTPS GitHub Pages site URL")
    manifest_path = Path(manifest_path)
    manifest_bytes = manifest_path.read_bytes()
    if manifest_path.name != "release.json":
        raise ValueError("Use the exported release.json manifest")
    manifest = verify_release_directory(manifest_path.parent, run_id)
    snapshot, files = release_files(store, run_id)
    expected = {path: hashlib.sha256(data).hexdigest() for path, data in files.items()}
    if manifest["files"] != expected or manifest["stories"] != len(snapshot["stories"]):
        raise ValueError("Release content does not match the retained edition")
    site_url = site_url.rstrip("/") + "/"
    if json.loads(fetch_public_file(site_url + "release.json")) != manifest:
        raise ValueError("Deployed release manifest does not match the candidate")
    for path, expected in manifest["files"].items():
        local = manifest_path.parent / path
        if (
            local.is_symlink()
            or hashlib.sha256(local.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Local release changed after export")
        if hashlib.sha256(fetch_public_file(site_url + path)).hexdigest() != expected:
            raise ValueError("Delivered artifact differs from the exported release")
    receipt = {
        "public_url": site_url,
        "release_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "files_verified": len(manifest["files"]),
    }
    return store.record_publication(run_id, receipt)
