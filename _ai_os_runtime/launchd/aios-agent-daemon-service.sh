#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/opt/postgresql@15/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export AI_OS_RUNTIME_ROOT="${AI_OS_RUNTIME_ROOT:-/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime}"
export AI_OS_VAULT_ROOT="${AI_OS_VAULT_ROOT:-/Volumes/Devarsh SSD/Obsidian memory }"
export AI_OS_PSQL_BIN="${AI_OS_PSQL_BIN:-/opt/homebrew/opt/postgresql@15/bin/psql}"
export AI_OS_DOCKER_BIN="${AI_OS_DOCKER_BIN:-/usr/local/bin/docker}"
export AI_OS_AGENT_DAEMON_INTERVAL="${AI_OS_AGENT_DAEMON_INTERVAL:-45}"
export AI_OS_ENABLE_SOURCE_FRESHNESS_SCHEDULER="${AI_OS_ENABLE_SOURCE_FRESHNESS_SCHEDULER:-1}"
export AI_OS_SOURCE_FRESHNESS_INTERVAL_SECONDS="${AI_OS_SOURCE_FRESHNESS_INTERVAL_SECONDS:-900}"
export AI_OS_SOURCE_FRESHNESS_LIMIT="${AI_OS_SOURCE_FRESHNESS_LIMIT:-100}"
export AI_OS_SOURCE_FRESHNESS_TIMEOUT_SECONDS="${AI_OS_SOURCE_FRESHNESS_TIMEOUT_SECONDS:-180}"
export AI_OS_ENABLE_TRADINGVIEW_CDP_CHECKER="${AI_OS_ENABLE_TRADINGVIEW_CDP_CHECKER:-1}"
export AI_OS_TRADINGVIEW_CDP_CHECK_INTERVAL_SECONDS="${AI_OS_TRADINGVIEW_CDP_CHECK_INTERVAL_SECONDS:-60}"
export AI_OS_TRADINGVIEW_CDP_CHECK_TIMEOUT_SECONDS="${AI_OS_TRADINGVIEW_CDP_CHECK_TIMEOUT_SECONDS:-3}"
export AI_OS_ENABLE_OHLCV_AGGREGATION="${AI_OS_ENABLE_OHLCV_AGGREGATION:-1}"
export AI_OS_OHLCV_AGGREGATION_INTERVAL_SECONDS="${AI_OS_OHLCV_AGGREGATION_INTERVAL_SECONDS:-300}"
export AI_OS_OHLCV_AGGREGATION_TIMEOUT_SECONDS="${AI_OS_OHLCV_AGGREGATION_TIMEOUT_SECONDS:-120}"

cd "/Users/devarshthakkar/Library/Application Support/AIOS/service"
exec python3 -u scripts/run_agent_message_daemon.py \
  --interval "${AI_OS_AGENT_DAEMON_INTERVAL}" \
  --source-freshness-interval "${AI_OS_SOURCE_FRESHNESS_INTERVAL_SECONDS}" \
  --source-freshness-limit "${AI_OS_SOURCE_FRESHNESS_LIMIT}" \
  --source-freshness-timeout "${AI_OS_SOURCE_FRESHNESS_TIMEOUT_SECONDS}" \
  --tradingview-cdp-check-interval "${AI_OS_TRADINGVIEW_CDP_CHECK_INTERVAL_SECONDS}" \
  --tradingview-cdp-check-timeout "${AI_OS_TRADINGVIEW_CDP_CHECK_TIMEOUT_SECONDS}" \
  --ohlcv-aggregation-interval "${AI_OS_OHLCV_AGGREGATION_INTERVAL_SECONDS}" \
  --ohlcv-aggregation-timeout "${AI_OS_OHLCV_AGGREGATION_TIMEOUT_SECONDS}" \
  --message-limit 10 \
  --worker-limit 5
