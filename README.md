# NutriCare

料理名から34項目の栄養素をGemini AIで推定する栄養管理アプリ。

## セットアップ
1. `.env.example` を `.env` にコピーし、`GEMINI_API_KEY` を設定
2. `python server.py`
3. ブラウザで http://localhost:8000 を開く

## 注意
`.env` は `.gitignore` 済みのためGitに含まれません。APIキーはコードに直接書かないでください。
