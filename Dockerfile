# Pythonの公式イメージをベースにする
FROM python:3.10-slim

# 作業ディレクトリを設定
WORKDIR /app

# 必要なファイルをコンテナにコピー
COPY ./slackbot_jsl ./slackbot_jsl
COPY ./requirements.txt .
# 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# 環境変数を設定（必要に応じて）
# ENV SLACK_BOT_TOKEN=your-token
# ENV OPENAI_API_KEY=your-api-key

# アプリケーションを実行
CMD ["python", "./slackbot_jsl/app.py"]
