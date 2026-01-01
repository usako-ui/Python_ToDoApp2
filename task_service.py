# task_service.py
import gspread
import json
import os
from datetime import datetime
from google.oauth2.service_account import Credentials

# --------------------
# 環境変数
# --------------------
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# --------------------
# Sheet取得
# --------------------
def get_sheet():
    if SERVICE_ACCOUNT_JSON:
        info = json.loads(SERVICE_ACCOUNT_JSON)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )

    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1


# --------------------
# 次のタスクID
# --------------------
def generate_next_task_id(sheet):
    records = sheet.get_all_records()
    ids = []

    for r in records:
        try:
            ids.append(int(r.get("タスクID", 0)))
        except:
            pass

    next_id = max(ids) + 1 if ids else 1
    return str(next_id).zfill(3)


# --------------------
# シート → タスク一覧
# --------------------
def sheet_to_tasks(sheet):
    records = sheet.get_all_records()
    tasks = []

    for r in records:
        tasks.append({
            "ID": str(r.get("タスクID", "")).strip(),
            "Title": r.get("タイトル", "").strip(),
            "Content": r.get("内容", ""),
            "DueDate": r.get("期日", ""),
            "Completed": str(r.get("完了フラグ", "")).lower() == "true",
            "Source": r.get("登録元", "manual"),
            "EventID": r.get("イベントID", ""),
            "Category": r.get("カテゴリ", ""),
            "Priority": r.get("優先度", "中")
        })

    def parse_due(d):
        if not d:
            return datetime.max
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(d, fmt)
            except:
                pass
        return datetime.max

    # 優先度 → 数値
    priority_order = {"高": 0, "中": 1, "低": 2}

    return sorted(
        tasks,
        key=lambda x: (
            priority_order.get(x["Priority"], 1),
            parse_due(x["DueDate"])
        )
    )


# --------------------
# タスク追加
# --------------------
def add_task(sheet, title, content, duedate, category, priority):
    task_id = generate_next_task_id(sheet)

    sheet.append_row([
        task_id,
        title,
        content,
        duedate,
        "False",
        "manual",
        "",
        category,
        priority
    ])

    return task_id
