#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime_root="$(cd "${script_dir}/.." && pwd)"
support_root="${AI_OS_MACBOOK_ROOT:-${HOME}/Library/Application Support/AIOS}"
bin_dir="${support_root}/bin"
log_dir="${HOME}/Library/Logs/AIOS"
launch_agents_dir="${HOME}/Library/LaunchAgents"
source_script="${runtime_root}/scripts/start_mlx_workhorse.sh"
source_plist="${runtime_root}/launchd/com.devarsh.aios.charlie-mlx.plist"
target_script="${bin_dir}/start-charlie-qwen35.sh"
target_plist="${launch_agents_dir}/com.devarsh.aios.charlie-mlx.plist"
launch_domain="gui/$(id -u)"
label="com.devarsh.aios.charlie-mlx"
health_url="${AI_OS_MLX_HEALTH_URL:-http://100.75.156.32:11436/v1/models}"

[[ -x "${support_root}/venvs/mlx-vlm/bin/mlx_vlm.server" ]] || {
  printf "Missing pinned MLX-VLM environment under %s\n" "${support_root}/venvs/mlx-vlm" >&2
  exit 3
}
[[ -f "${support_root}/models/qwen3.5-9b-4bit-8b2b98c/config.json" ]] || {
  printf "Missing qualified Qwen3.5 weights under %s\n" "${support_root}/models" >&2
  exit 4
}

mkdir -p "${bin_dir}" "${log_dir}" "${launch_agents_dir}"
cp -f "${source_script}" "${target_script}"
cp -f "${source_plist}" "${target_plist}"
chmod 755 "${target_script}"
chmod 644 "${target_plist}"
plutil -lint "${target_plist}" >/dev/null

launchctl bootout "${launch_domain}" "${target_plist}" 2>/dev/null || true
launchctl bootstrap "${launch_domain}" "${target_plist}"
launchctl kickstart -k "${launch_domain}/${label}"

for _ in $(seq 1 60); do
  if curl --max-time 2 -fsS "${health_url}" >/dev/null 2>&1; then
    printf "Qualified Charlie model service is healthy at %s\n" "${health_url}"
    exit 0
  fi
  sleep 1
done

printf "Charlie model service did not become healthy. See %s\n" "${log_dir}/charlie-qwen35.error.log" >&2
exit 5
