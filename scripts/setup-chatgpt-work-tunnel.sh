#!/usr/bin/env bash

set -euo pipefail

PROFILE_NAME="${SUBSTACK_TUNNEL_PROFILE:-substack-mcp}"
REPO_DIR="${SUBSTACK_MCP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VENV_DIR="${REPO_DIR}/.venv"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This helper is intended for macOS because Substack authentication is read from a local browser session." >&2
  exit 1
fi

if [[ -z "${SUBSTACK_TUNNEL_ID:-}" ]]; then
  echo "Set SUBSTACK_TUNNEL_ID to the tunnel ID created in OpenAI Platform settings." >&2
  exit 1
fi

if [[ -z "${CONTROL_PLANE_API_KEY:-}" ]]; then
  echo "Set CONTROL_PLANE_API_KEY to the runtime API key created for tunnel-client." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

if ! command -v tunnel-client >/dev/null 2>&1; then
  echo "tunnel-client is required. Download it from OpenAI Platform tunnel settings." >&2
  exit 1
fi

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/pip" install -e "${REPO_DIR}"

echo "Opening the local Substack authentication setup. No session token is printed or uploaded by this script."
"${VENV_DIR}/bin/substack-mcp-setup"

tunnel-client init \
  --sample sample_mcp_stdio_local \
  --profile "${PROFILE_NAME}" \
  --tunnel-id "${SUBSTACK_TUNNEL_ID}" \
  --mcp-command "${VENV_DIR}/bin/substack-mcp"

tunnel-client doctor --profile "${PROFILE_NAME}" --explain

echo
echo "Setup complete. Keep the following process running while ChatGPT Work uses Substack:"
echo "tunnel-client run --profile ${PROFILE_NAME}"

