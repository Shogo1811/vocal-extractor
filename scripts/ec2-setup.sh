#!/bin/bash
# EC2 Ubuntu 22.04 セットアップスクリプト
# 使用方法: sudo bash ec2-setup.sh

set -e

echo "=== Vocal Extractor EC2 セットアップ ==="

# システムアップデート
echo "[1/5] システムアップデート中..."
apt-get update && apt-get upgrade -y

# Docker インストール
echo "[2/5] Docker インストール中..."
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Docker を ubuntu ユーザーで使えるようにする
echo "[3/5] Docker 権限設定中..."
usermod -aG docker ubuntu

# スワップ領域追加（メモリ不足対策）
echo "[4/5] スワップ領域設定中..."
if [ ! -f /swapfile ]; then
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# ファイアウォール設定
echo "[5/5] ファイアウォール設定中..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp
ufw --force enable

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "次のステップ:"
echo "1. 一度ログアウトして再ログイン（Docker権限反映のため）"
echo "2. アプリケーションをデプロイ:"
echo "   cd /home/ubuntu/vocal-extractor"
echo "   docker compose up -d --build"
echo ""
echo "アクセス: http://<EC2のパブリックIP>:8000"
