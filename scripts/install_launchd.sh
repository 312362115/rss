#!/usr/bin/env bash
# 安装 / 卸载 launchd 定时任务。
#
# 用法:
#   ./scripts/install_launchd.sh install   # 加载定时任务
#   ./scripts/install_launchd.sh uninstall # 卸载
#   ./scripts/install_launchd.sh status    # 查看状态
#   ./scripts/install_launchd.sh logs      # 查看最近日志

set -euo pipefail

LABEL="com.renlongyu.rss"
PLIST_NAME="${LABEL}.plist"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_PLIST="${REPO_ROOT}/launchd/${PLIST_NAME}"
DEST_DIR="${HOME}/Library/LaunchAgents"
DEST_PLIST="${DEST_DIR}/${PLIST_NAME}"

cmd="${1:-install}"

case "$cmd" in
  install)
    mkdir -p "$DEST_DIR"
    cp "$SRC_PLIST" "$DEST_PLIST"
    launchctl unload "$DEST_PLIST" 2>/dev/null || true
    launchctl load -w "$DEST_PLIST"
    echo "✓ loaded $LABEL"
    launchctl list | grep "$LABEL" || true
    ;;
  uninstall)
    if [ -f "$DEST_PLIST" ]; then
      launchctl unload "$DEST_PLIST" 2>/dev/null || true
      rm "$DEST_PLIST"
      echo "✓ unloaded $LABEL"
    else
      echo "not installed"
    fi
    ;;
  status)
    echo "--- launchctl list ---"
    launchctl list | grep "$LABEL" || echo "(not loaded)"
    echo "--- plist ---"
    [ -f "$DEST_PLIST" ] && echo "installed at: $DEST_PLIST" || echo "(not installed)"
    ;;
  logs)
    echo "--- stdout (tail) ---"
    tail -n 50 /tmp/rss-daily.log 2>/dev/null || echo "(no stdout log yet)"
    echo
    echo "--- stderr (tail) ---"
    tail -n 50 /tmp/rss-daily.err 2>/dev/null || echo "(no stderr log yet)"
    ;;
  *)
    echo "usage: $0 {install|uninstall|status|logs}" >&2
    exit 1
    ;;
esac
