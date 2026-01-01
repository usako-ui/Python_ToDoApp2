from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# サービス層
from task_service import (
    get_sheet,
    sheet_to_tasks,
    add_task
)

# --------------------
# 環境変数
# --------------------
load_dotenv()

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "replace-me")

# --------------------
# Flask
# --------------------
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY


# --------------------
# 期日を安全に datetime に変換
# --------------------
def parse_due(task):
    """
    task["_due"] を datetime に正規化
    """
    if isinstance(task.get("_due"), datetime):
        return task["_due"]

    due_str = task.get("DueDate") or ""
    try:
        task["_due"] = datetime.fromisoformat(due_str)
    except Exception:
        task["_due"] = None

    return task["_due"] or datetime.max


# --------------------
# トップ
# --------------------
@app.route("/")
def index():
    sheet = get_sheet()
    tasks = sheet_to_tasks(sheet)

    # _due を必ずセット
    for t in tasks:
        parse_due(t)

    tasks.sort(key=parse_due)

    return render_template(
        "index.html",
        tasks=tasks,
        now=datetime.now()   # ★ datetime のまま
    )


# --------------------
# 一覧（フィルタ・ソート対応）
# --------------------
@app.route("/tasks")
def task_list():
    sheet = get_sheet()
    tasks = sheet_to_tasks(sheet)

    # _due を必ずセット
    for t in tasks:
        parse_due(t)

    filter_mode = request.args.get("filter")
    category = request.args.get("category")
    sort_mode = request.args.get("sort")

    # ---- 未完了のみ ----
    if filter_mode == "todo":
        tasks = [t for t in tasks if not t.get("Completed")]

    # ---- カテゴリ抽出 ----
    if category:
        tasks = [t for t in tasks if t.get("Category") == category]

    # ---- 並び替え ----
    if sort_mode == "priority":
        priority_order = {"高": 0, "中": 1, "低": 2}
        tasks.sort(
            key=lambda t: priority_order.get(t.get("Priority", "中"), 1)
        )
    else:
        tasks.sort(key=parse_due)

    return render_template(
        "tasks.html",
        tasks=tasks,
        filter_mode=filter_mode,
        category=category,
        sort_mode=sort_mode,
        now=datetime.now()   # ★ ここが超重要
    )


# --------------------
# 追加
# --------------------
@app.route("/add", methods=["POST"])
def add():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    duedate = request.form.get("duedate", "").strip()
    category = request.form.get("category", "").strip()
    priority = request.form.get("priority", "中")

    if not title or not duedate:
        flash("タイトルと期日は必須です。")
        return redirect(url_for("index"))

    sheet = get_sheet()
    add_task(
        sheet,
        title,
        content,
        duedate,
        category,
        priority
    )

    flash("タスクを追加しました。")
    return redirect(url_for("index"))


# --------------------
# 編集
# --------------------
@app.route("/edit/<task_id>")
def edit(task_id):
    sheet = get_sheet()
    records = sheet.get_all_records()

    for r in records:
        if str(r.get("タスクID", "")).strip() == task_id:
            task = {
                "ID": task_id,
                "Title": r.get("タイトル", ""),
                "Content": r.get("内容", ""),
                "DueDate": r.get("期日", ""),
                "Category": r.get("カテゴリ", ""),
                "Priority": r.get("優先度", "中")
            }
            return render_template("edit.html", task=task)

    flash("タスクが見つかりません。")
    return redirect(url_for("task_list"))


# --------------------
# 更新
# --------------------
@app.route("/update/<task_id>", methods=["POST"])
def update(task_id):
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    duedate = request.form.get("duedate", "").strip()
    category = request.form.get("category", "").strip()
    priority = request.form.get("priority", "中")

    if not title or not duedate:
        flash("タイトルと期日は必須です。")
        return redirect(url_for("task_list"))

    sheet = get_sheet()
    records = sheet.get_all_records()

    for idx, r in enumerate(records, start=2):
        if str(r.get("タスクID", "")).strip() == task_id:
            sheet.update(
                f"A{idx}:I{idx}",
                [[
                    task_id,
                    title,
                    content,
                    duedate,
                    r.get("完了フラグ", "False"),
                    r.get("登録元", "manual"),
                    r.get("イベントID", ""),
                    category,
                    priority
                ]]
            )
            flash("タスクを更新しました。")
            return redirect(url_for("task_list"))

    flash("タスクが見つかりません。")
    return redirect(url_for("task_list"))


# --------------------
# 完了切替
# --------------------
@app.route("/toggle/<task_id>", methods=["POST"])
def toggle(task_id):
    sheet = get_sheet()
    records = sheet.get_all_records()

    for idx, r in enumerate(records, start=2):
        if str(r.get("タスクID", "")).strip() == task_id:
            current = str(r.get("完了フラグ", "")).lower() == "true"
            sheet.update_cell(idx, 5, "False" if current else "True")
            return redirect(request.referrer or url_for("task_list"))

    flash("タスクが見つかりません。")
    return redirect(url_for("task_list"))


# --------------------
# 削除
# --------------------
@app.route("/delete/<task_id>", methods=["POST"])
def delete(task_id):
    sheet = get_sheet()
    records = sheet.get_all_records()

    for idx, r in enumerate(records, start=2):
        if str(r.get("タスクID", "")).strip() == task_id:
            sheet.delete_rows(idx)
            flash("タスクを削除しました。")
            return redirect(url_for("task_list"))

    flash("タスクが見つかりません。")
    return redirect(url_for("task_list"))


# --------------------
# 完了タスク一括削除
# --------------------
@app.route("/delete_completed", methods=["POST"])
def delete_completed():
    sheet = get_sheet()
    records = sheet.get_all_records()

    for idx in range(len(records), 0, -1):
        r = records[idx - 1]
        if str(r.get("完了フラグ", "")).lower() == "true":
            sheet.delete_rows(idx + 1)

    flash("完了済みタスクを一括削除しました。")
    return redirect(url_for("task_list"))


# --------------------
# 実行
# --------------------
if __name__ == "__main__":
    app.run(debug=True)
