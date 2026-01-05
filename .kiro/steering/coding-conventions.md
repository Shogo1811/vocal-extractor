# Coding Conventions

このプロジェクトのコーディング規約を定義します。

## Python スタイルガイド

### 全般

- Python 3.10以上を使用
- PEP 8に準拠
- 最大行長: 100文字
- インデント: スペース4つ

### 命名規則

| 対象 | 規則 | 例 |
|------|------|-----|
| 変数・関数 | snake_case | `job_status`, `process_audio()` |
| クラス | PascalCase | `JobManager`, `AudioFileInfo` |
| 定数 | UPPER_SNAKE_CASE | `MAX_FILE_SIZE`, `DEFAULT_TIMEOUT` |
| プライベート | 先頭にアンダースコア | `_internal_method()` |

### 型アノテーション

- すべての関数に型アノテーションを付ける
- Pydantic モデルのフィールドには必ず型を指定
- `Optional` は None を許容する場合のみ使用
- Python 3.10以上のビルトイン型を使用（`list[str]` など）

```python
# Good
def process_file(file_path: str, timeout: int = 30) -> ProcessingResult:
    ...

# Bad
def process_file(file_path, timeout=30):
    ...
```

### Docstring

- すべてのモジュール、クラス、関数に docstring を付ける
- ダブルクォート3つを使用
- 1行で収まる場合は1行で記述

```python
"""Short description."""

"""
Longer description that spans
multiple lines.
"""
```

## ファイル構成

### ディレクトリ構造

```
app/
├── __init__.py
├── main.py           # FastAPI アプリケーションエントリポイント
├── config.py         # 設定
├── logging_config.py # ロギング設定
├── models/           # Pydantic モデル
├── routers/          # API ルーター
├── services/         # ビジネスロジック
├── static/           # 静的ファイル
└── templates/        # Jinja2 テンプレート
```

### インポート順序

1. 標準ライブラリ
2. サードパーティライブラリ
3. ローカルモジュール

```python
# Standard library
import os
from datetime import datetime
from pathlib import Path

# Third party
from fastapi import FastAPI, Request
from pydantic import BaseModel

# Local
from app.config import settings
from app.services.job_manager import job_manager
```

## FastAPI / Pydantic

### エンドポイント

- 非同期関数として定義（`async def`）
- 適切な response_class を指定
- パスパラメータ、クエリパラメータには型を指定

```python
@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    """Get job status by ID."""
    ...
```

### Pydantic モデル

- `BaseModel` を継承
- フィールドには `Field()` でメタデータを追加
- バリデーションには Pydantic の機能を活用

```python
class Job(BaseModel):
    """Processing job model."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
```

## エラーハンドリング

- 具体的な例外をキャッチ
- ログにはコンテキスト情報を含める
- ユーザー向けエラーメッセージは分かりやすく

```python
try:
    result = await process_audio(file_path)
except FileNotFoundError:
    logger.error(f"File not found: {file_path}")
    raise HTTPException(status_code=404, detail="File not found")
except Exception as e:
    logger.exception(f"Unexpected error processing {file_path}")
    raise HTTPException(status_code=500, detail="Processing failed")
```

## ロギング

- `app.logging_config.logger` を使用
- 適切なログレベルを選択
  - `debug`: 開発時のデバッグ情報
  - `info`: 通常の動作情報
  - `warning`: 警告（処理は継続）
  - `error`: エラー（処理失敗）
  - `exception`: 例外（スタックトレース付き）

## 非推奨パターン

- `print()` でのデバッグ出力（logger を使用）
- `*` でのワイルドカードインポート
- ベア except 節（`except:` ではなく `except Exception:`）
- グローバル変数の多用
