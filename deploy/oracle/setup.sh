#!/usr/bin/env bash
# CivilBot: one-shot install on a FREE Oracle Cloud "Always Free" Ampere A1 VM (Ubuntu 22.04/24.04, ARM64)
#   2 OCPU / 12 GB RAM free forever → WORKERS=2
# Usage (on the VM):  curl -fsSL <raw-url>/deploy/oracle/setup.sh | bash      or   bash setup.sh
set -euo pipefail
APP_DIR=${APP_DIR:-$HOME/civilbot}

echo "==> Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo "==> Swap 2G (safety net for PDF rendering spikes)"
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

echo "==> Firewall: open 80/443 (Oracle images ship with iptables REJECT rules)"
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT || true
sudo sh -c 'command -v netfilter-persistent >/dev/null && netfilter-persistent save' || true

cd "$APP_DIR"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "!! عدّل الملف $APP_DIR/.env (BOT_TOKEN, ADMIN_IDS, DOMAIN) ثم شغّل السكربت مرة ثانية"
  exit 1
fi

echo "==> Build & start (bot + api + caddy https)"
sudo docker compose -f docker-compose.yml -f deploy/oracle/compose.oracle.yml up -d --build
sudo docker compose ps
echo "✅ تم. البوت يشتغل، والتطبيق على https://\$DOMAIN"
