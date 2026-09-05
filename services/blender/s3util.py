from __future__ import annotations

import os
from pathlib import Path

import boto3
from botocore.client import Config


def client():
    endpoint = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
        region_name=os.environ.get("S3_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def upload_file(path: Path, key: str, content_type: str) -> dict:
    bucket = os.environ.get("S3_BUCKET", "aai-artifacts")
    c = client()
    extra = {"ContentType": content_type}
    c.upload_file(str(path), bucket, key, ExtraArgs=extra)
    size = path.stat().st_size
    return {"bucket": bucket, "key": key, "bytes": size, "content_type": content_type}
