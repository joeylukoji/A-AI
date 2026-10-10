"""Export existing generation previews and original briefs from local Docker stores."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
from pathlib import Path

import boto3
from botocore.config import Config
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/articles/selection-generations"
QUERY = """
SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json) FROM (
 SELECT j.id AS job_id, j.created_at, j.input->>'brief' AS brief,
        j.input->'constraints' AS constraints, r.id AS revision_id,
        r.version, r.preview_key, j.output->'provenance' AS provenance
 FROM jobs j JOIN plan_revisions r ON r.id::text = j.output->>'revision_id'
 WHERE j.type='generate_2d' AND j.status='succeeded' AND r.source='ai'
   AND r.preview_key IS NOT NULL AND r.preview_key <> ''
 ORDER BY j.created_at DESC, j.id
) t
"""


def docker_json(arguments: list[str]) -> object:
    """Run a read-only Docker command and decode its JSON output."""
    result = subprocess.run(["docker", *arguments], check=True, capture_output=True, encoding="utf-8")
    return json.loads(result.stdout)


def export() -> None:
    """Copy available original objects into a fresh local output directory."""
    rows = docker_json([
        "exec", "-e", "PGOPTIONS=-c default_transaction_read_only=on",
        "deploy-postgres-1", "psql", "-X", "-U", "aai", "-d", "aai",
        "-A", "-t", "-q", "-v", "ON_ERROR_STOP=1", "-c", QUERY,
    ])
    assert isinstance(rows, list)
    containers = docker_json(["inspect", "deploy-minio-1"])
    if not isinstance(containers, list) or not containers or not isinstance(containers[0], dict):
        raise ValueError("Unexpected Docker inspect response")
    container = containers[0]
    environment = dict(entry.split("=", 1) for entry in container["Config"]["Env"] if "=" in entry)
    client = boto3.client(
        "s3", endpoint_url="http://127.0.0.1:9000",
        aws_access_key_id=environment["MINIO_ROOT_USER"],
        aws_secret_access_key=environment["MINIO_ROOT_PASSWORD"],
        region_name="us-east-1", config=Config(signature_version="s3v4"),
    )
    OUTPUT.mkdir(parents=True, exist_ok=False)
    (OUTPUT / "images").mkdir()
    manifest = []
    for number, row in enumerate(rows, 1):
        entry = {"number": number, **row}
        try:
            response = client.get_object(Bucket="aai-artifacts", Key=row["preview_key"])
            body = response["Body"]
            try:
                data = body.read()
            finally:
                body.close()
            with Image.open(io.BytesIO(data)) as picture:
                picture.load()
                entry.update(width=picture.width, height=picture.height, format=picture.format)
                entry["image_metadata_keys"] = sorted(picture.info)
                extension = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}[picture.format]
            filename = f"images/generation-{number:03d}.{extension}"
            (OUTPUT / filename).write_bytes(data)
            entry.update(file=filename, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            entry["storage_metadata"] = {
                key: value for key, value in response.get("Metadata", {}).items()
                if key.lower() in {"model", "provider", "generator", "backend"}
            }
            print(f"{number:03d} {entry['width']}x{entry['height']} {entry['format']} {len(data)} bytes")
        except Exception as exc:
            entry["export_error"] = type(exc).__name__
            print(f"{number:03d} unavailable: {type(exc).__name__}")
        manifest.append(entry)
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Exported {sum('file' in entry for entry in manifest)} / {len(manifest)} images")


if __name__ == "__main__":
    export()
