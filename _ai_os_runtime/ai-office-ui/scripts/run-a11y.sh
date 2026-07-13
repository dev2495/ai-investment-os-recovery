#!/usr/bin/env bash
set -euo pipefail

for shard in 1 2 3 4; do
  echo "Running accessibility shard ${shard}/4"
  npx playwright test tests/a11y.spec.ts --shard="${shard}/4" --workers=1 --reporter=dot
done
