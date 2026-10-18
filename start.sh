#!/bin/sh
# SERVICE=bot (default) -> Telegram bot (polling)   |   SERVICE=api -> web app + API (needs PORT, set by Railway)
mkdir -p "$(dirname "${CIVILBOT_DB:-/data/civilbot.sqlite3}")" "${BACKUP_DIR:-/data/backups}" 2>/dev/null
case "${SERVICE:-bot}" in
  api) exec python -m civilbot.api ;;
  *)   exec python -m civilbot.bot.main ;;
esac
