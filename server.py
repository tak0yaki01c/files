"""NutriCare ローカルサーバー

- index.html を配信します
- /api/analyze で Gemini API を代理呼び出しします
- APIキーは .env（または環境変数）から読み込み、ブラウザには一切渡しません

使い方:  python server.py  →  http://localhost:8000
"""
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL = "gemini-3-flash-preview"
PORT = int(os.environ.get("PORT", "8000"))

NUTRIENT_LIST = [
    "エネルギー", "タンパク質", "脂質", "飽和脂肪酸", "n-6系脂肪酸", "n-3系脂肪酸",
    "炭水化物", "食物繊維", "ビタミンA", "ビタミンD", "ビタミンE", "ビタミンK",
    "ビタミンB1", "ビタミンB2", "ビタミンB6", "ビタミンB12", "ナイアシン", "葉酸",
    "パントテン酸", "ビオチン", "ビタミンC", "ナトリウム（食塩相当量）", "カリウム",
    "カルシウム", "マグネシウム", "リン", "鉄", "亜鉛", "銅", "マンガン",
    "ヨウ素", "セレン", "クロム", "モリブデン",
]


def load_env():
    """.env を読み込む（python-dotenv 不要の簡易版）"""
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def build_prompt(dish, age, gender):
    return f"""
あなたは精密な栄養計算管理システムです。
入力された料理名: 「{dish}」

【タスク】
1. まず「{dish}」が実在する料理・食品かどうか判定してください。架空の言葉や食べ物でない場合は exists: false としてください。
2. 実在する場合、1人前に使われる主な材料と使用量を推定してください（水・調味料・油も含め、多くても15品目まで。量は g、ml、個などで具体的に）。
3. 以下の34項目の栄養素は、必ず手順2で挙げた材料と使用量から積み上げて計算してください。材料の量と栄養素の値が矛盾しないようにすることが最重要です。
4. 日本人の食事摂取基準に基づき、{age}歳・{gender}における各栄養素の1日あたりの「推奨量/目安量/目標量」を算出して添えてください。
5. 含有量がほぼ0の項目は amount: "0g" のように0で回答してください。

対象の34項目:
{', '.join(NUTRIENT_LIST)}

【出力フォーマット】
以下の純粋なJSONのみを出力してください。Markdown等の装飾テキストは含めないでください。
ingredients は nutrients より先に出力してください。exists が false の場合、ingredients と nutrients は空配列にしてください。
{{
  "exists": true,
  "ingredients": [
    {{ "name": "にんじん", "amount": "50g" }},
    {{ "name": "水", "amount": "200ml" }}
  ],
  "nutrients": [
    {{ "name": "エネルギー", "amount": "650kcal", "recommended": "2300kcal/日" }}
  ]
}}
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, ctype="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (BASE_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        if self.path != "/api/analyze":
            return self._send(404, b'{"error":"not found"}')

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return self._send(500, json.dumps({"error": "GEMINI_API_KEY が未設定です (.env を確認)"}).encode())

        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
            dish = str(req.get("dish", "")).strip()[:100]
            age = int(req.get("age"))
            gender = str(req.get("gender", ""))[:10]
            if not dish:
                raise ValueError("dish is empty")
        except (ValueError, TypeError, json.JSONDecodeError):
            return self._send(400, b'{"error":"invalid request"}')

        payload = {
            "contents": [{"parts": [{"text": build_prompt(dish, age, gender)}]}],
            # JSON形式で返すよう指定（材料と栄養素を同時に安定して取得するため）
            "generationConfig": {"responseMimeType": "application/json"},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
        gemini_req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(gemini_req, timeout=60) as res:
                self._send(200, res.read())
        except urllib.error.HTTPError as e:
            self._send(e.code, e.read())
        except Exception:
            self._send(502, b'{"error":"upstream error"}')


if __name__ == "__main__":
    load_env()
    # 自分のPCからのみアクセス可能（127.0.0.1）
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"NutriCare 起動: http://localhost:{PORT}  (Ctrl+C で停止)")
    server.serve_forever()
