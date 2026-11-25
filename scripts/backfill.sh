#!/usr/bin/env bash
set -euo pipefail

# Backfill month by month. Each iteration is a separate, tracked pipeline run.
# End date is exclusive.
while read -r from to; do
  docker compose run --rm pipeline python -m pipeline.cli --mode backfill --from "$from" --to "$to"
done <<EOF
2025-01-01 2025-02-01
2025-02-01 2025-03-01
2025-03-01 2025-04-01
2025-04-01 2025-05-01
2025-05-01 2025-06-01
EOF
