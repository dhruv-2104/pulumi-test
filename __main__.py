"""
Pulumi program for tenant bucket provisioning.

Reads bucket definitions from buckets.yaml (same folder) and creates
one gcp.storage.Bucket per entry. This file is written once and never
touched per-request — buckets.yaml is the only thing that changes.

Expected buckets.yaml shape:

buckets:

name: uploads
    location: asia-south1
    storage_class: STANDARD      # optional, defaults to STANDARD
    versioning: false            # optional, defaults to false
    force_destroy: false         # optional — if true, allows delete even if non-empty

Adding a bucket = append an entry here and commit.
Removing a bucket = delete the entry — PKO's next pulumi up will destroy it.
"""

import os
import yaml
import pulumi
import pulumi_gcp as gcp

# --- load manifest -----------------------------------------------------

MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "buckets.yaml")

with open(MANIFEST_PATH) as f:
    manifest = yaml.safe_load(f) or {}

bucket_specs = manifest.get("buckets", [])

if not bucket_specs:
    pulumi.log.warn("No buckets defined in buckets.yaml — nothing to provision")

# --- config: tenant prefix so bucket names don't collide globally -------
# GCS bucket names are globally unique across ALL of GCP, not just your
# project, so a raw "uploads" name will collide across tenants. Prefix it.

config = pulumi.Config()
tenant_id = config.require("tenant_id")

# --- create one bucket per manifest entry -------------------------------

created_buckets = {}

for spec in bucket_specs:
    logical_name = spec[
        "name"
    ]  # used as Pulumi's logical resource name — keep stable, don't rename after creation
    real_bucket_name = f"{tenant_id}-{logical_name}"

    bucket = gcp.storage.Bucket(
        logical_name,
        name=real_bucket_name,
        location=spec.get("location", "asia-south1"),
        storage_class=spec.get("storage_class", "STANDARD"),
        versioning=gcp.storage.BucketVersioningArgs(
            enabled=spec.get("versioning", False),
        ),
        force_destroy=spec.get("force_destroy", False),
        uniform_bucket_level_access=True,  # recommended default, avoids legacy ACL surprises
    )

    created_buckets[logical_name] = bucket

# --- stack outputs (visible via `pulumi stack output`, useful for status DB) --

pulumi.export(
    "bucket_names", {name: bucket.name for name, bucket in created_buckets.items()}
)
pulumi.export("bucket_count", len(created_buckets))