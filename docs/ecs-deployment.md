# ECS Fargate デプロイ手順（Terraform）

## 前提条件

- AWS CLI がインストール・設定済み
- Terraform がインストール済み（v1.0.0以上）
- Docker がインストール済み

## アーキテクチャ

```
Internet
    │
    ▼
┌─────────┐
│   ALB   │
└────┬────┘
     │
     ▼
┌─────────────────────────┐
│      ECS Fargate        │
│  ┌───────────────────┐  │
│  │  vocal-extractor  │  │
│  │    Container      │  │
│  └───────────────────┘  │
└─────────────────────────┘
     │
     ▼
┌─────────┐
│   ECR   │
└─────────┘
```

## デプロイ手順

### Step 1: AWS CLI 設定

```bash
aws configure
# AWS Access Key ID: あなたのアクセスキー
# AWS Secret Access Key: あなたのシークレットキー
# Default region name: ap-northeast-1
# Default output format: json
```

### Step 2: Terraform 初期化

```bash
cd terraform
terraform init
```

### Step 3: インフラ作成（プレビュー）

```bash
terraform plan
```

### Step 4: インフラ作成（実行）

```bash
terraform apply
```

`yes` を入力して実行。作成には5〜10分かかります。

### Step 5: ECR にログイン

```bash
# ECRリポジトリURLを取得
ECR_URL=$(terraform output -raw ecr_repository_url)

# ECRにログイン
aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin $ECR_URL
```

### Step 6: Docker イメージをビルド・プッシュ

```bash
# プロジェクトルートに戻る
cd ..

# イメージをビルド
docker build -t vocal-extractor .

# タグ付け
docker tag vocal-extractor:latest $ECR_URL:latest

# プッシュ
docker push $ECR_URL:latest
```

### Step 7: ECS サービスを更新

```bash
aws ecs update-service \
  --cluster vocal-extractor-cluster \
  --service vocal-extractor-service \
  --force-new-deployment \
  --region ap-northeast-1
```

### Step 8: 動作確認

```bash
cd terraform
APP_URL=$(terraform output -raw app_url)
echo "アプリURL: $APP_URL"
```

ブラウザで表示されたURLにアクセス。

---

## 運用コマンド

### ログ確認

```bash
aws logs tail /ecs/vocal-extractor --follow
```

### サービス状態確認

```bash
aws ecs describe-services \
  --cluster vocal-extractor-cluster \
  --services vocal-extractor-service \
  --region ap-northeast-1
```

### タスク一覧

```bash
aws ecs list-tasks \
  --cluster vocal-extractor-cluster \
  --region ap-northeast-1
```

### イメージ更新時のデプロイ

```bash
# 1. イメージをビルド・プッシュ
docker build -t vocal-extractor .
docker tag vocal-extractor:latest $ECR_URL:latest
docker push $ECR_URL:latest

# 2. サービスを更新
aws ecs update-service \
  --cluster vocal-extractor-cluster \
  --service vocal-extractor-service \
  --force-new-deployment \
  --region ap-northeast-1
```

---

## インフラ削除

```bash
cd terraform
terraform destroy
```

`yes` を入力して削除。

**注意**: ECRにイメージがあると削除に失敗する場合があります。その場合は先にイメージを削除してください。

```bash
aws ecr batch-delete-image \
  --repository-name vocal-extractor \
  --image-ids imageTag=latest \
  --region ap-northeast-1
```

---

## コスト目安

| リソース | 月額目安 |
|----------|----------|
| Fargate (1 vCPU, 4GB) | $40〜50 |
| ALB | $20〜25 |
| ECR | $1〜2 |
| データ転送 | 使用量による |
| **合計** | **$60〜80/月** |

---

## トラブルシューティング

### タスクが起動しない

```bash
# タスク停止理由を確認
aws ecs describe-tasks \
  --cluster vocal-extractor-cluster \
  --tasks $(aws ecs list-tasks --cluster vocal-extractor-cluster --query 'taskArns[0]' --output text) \
  --region ap-northeast-1
```

### ヘルスチェック失敗

1. セキュリティグループでポート8000が開放されているか確認
2. コンテナログを確認
3. `/health` エンドポイントが正常に応答するか確認

### イメージプッシュ失敗

```bash
# ECRに再ログイン
aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin $ECR_URL
```
