import os
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import requests

import gspread
from google.oauth2.service_account import Credentials


# =========================
# 環境変数読み込み
# =========================
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# ローカル用（jsonファイル）
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")

# GitHub Actions 用（JSON文字列）
SERVICE_ACCOUNT_JSON = os.getenv("SERVICE_ACCOUNT_JSON")

TASK_SHEET_NAME = "シート1"  # ← 固定


# =========================
# JST 定義
# =========================
JST = timezone(timedelta(hours=9))


# =========================
# Google Sheets 接続
# =========================
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # ---- GitHub Actions 環境 ----
    if os.getenv("GITHUB_ACTIONS") == "true" and SERVICE_ACCOUNT_JSON:
        credentials = Credentials.from_service_account_info(
            json.loads(SERVICE_ACCOUNT_JSON),
            scopes=scopes,
        )

    # ---- ローカル環境 ----
    else:
        credentials = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=scopes,
        )

    return gspread.authorize(credentials)


# =========================
# 今日・明日の未完了タスク取得（JST基準）
# =========================
def get_today_tomorrow_tasks():
    gc = get_gspread_client()
    ws = gc.open_by_key(SPREADSHEET_ID).worksheet(TASK_SHEET_NAME)

    records = ws.get_all_records()

    # ---- JST 基準の日付 ----
    today = datetime.now(JST).date()
    tomorrow = today + timedelta(days=1)

    result = []

    for r in records:
        # ---- 完了フラグ（TRUEは除外）----
        if str(r.get("完了フラグ", "")).lower() == "true":
            continue

        # ---- 期日 ----
        due_str = str(r.get("期日", "")).strip()
        if not due_str:
            continue

        try:
            # ISO形式を想定（スプレッドシート側）
            due_dt = datetime.fromisoformat(due_str)

            # タイムゾーンなし → JSTとして扱う
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=JST)
            else:
                due_dt = due_dt.astimezone(JST)

        except Exception:
            continue

        if due_dt.date() == today:
            label = "【今日】"
        elif due_dt.date() == tomorrow:
            label = "【明日】"
        else:
            continue

        result.append({
            "label": label,
            "title": r.get("タイトル", ""),
            "category": r.get("カテゴリ", "未分類"),
            "priority": r.get("優先度", "中"),
            "duedate": due_dt
        })

    # ---- 期日順 ----
    result.sort(key=lambda x: x["duedate"])
    return result


# =========================
# LINE メッセージ整形
# =========================
def build_message(tasks):
    if not tasks:
        return "📭 今日・明日期日の未完了タスクはありません。"

    lines = ["📌 今日・明日の未完了タスク\n"]

    for t in tasks:
        category_icon = {
            "仕事": "💼",
            "家庭": "🏠",
            "学習": "📓"
        }.get(t["category"], "📌")

        priority_icon = {
            "高": "🔴",
            "中": "🟡",
            "低": "⚪"
        }.get(t["priority"], "🟡")

        due_str = t["duedate"].strftime("%m/%d %H:%M")

        lines.append(
            f"{t['label']} {category_icon}{priority_icon}\n"
            f"{t['title']}\n"
            f"⏰ {due_str}"
        )

    return "\n\n".join(lines)


# =========================
# LINE Push 通知
# =========================
def push_line_message(message):
    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {"type": "text", "text": message}
        ]
    }

    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()


# =========================
# メイン処理
# =========================
def main():
    tasks = get_today_tomorrow_tasks()
    message = build_message(tasks)
    push_line_message(message)


if __name__ == "__main__":
    main()
