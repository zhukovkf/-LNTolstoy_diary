#!/usr/bin/env python3
"""
Ежедневный автопостинг дневника Л.Н. Толстого в Telegram-канал.

Как это работает:
- Читает tolstoy_diary_autopost_modern.csv (записи по порядку post_id)
- Смотрит в state.json, какая запись была опубликована последней
- Публикует следующую по порядку запись в канал
- Обновляет state.json

Запускать раз в день (см. README.md рядом с этим файлом — как настроить
автоматический запуск через GitHub Actions или обычный cron).
"""

import csv
import json
import os
import sys
import time
import urllib.request
import urllib.parse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.environ.get("TOLSTOY_CSV_PATH", os.path.join(SCRIPT_DIR, "tolstoy_diary_autopost_modern.csv"))
STATE_PATH = os.path.join(SCRIPT_DIR, "state.json")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "@LNTolstoy_diary")

TELEGRAM_MAX_LEN = 4096


def load_rows():
    with open(CSV_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"next_index": 0}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def format_message(row):
    date_label = row.get("date_original") or row["date"]
    header = f"\U0001F4D6 {date_label}"
    body = row["text"].strip()
    return f"{header}\n\n{body}"


def split_message(text, limit=TELEGRAM_MAX_LEN):
    """Split long text into Telegram-sized chunks, breaking on paragraph/sentence
    boundaries where possible so no word is cut in half."""
    if len(text) <= limit:
        return [text]

    parts = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n\n", 0, limit)
        if cut == -1:
            cut = remaining.rfind(". ", 0, limit)
        if cut == -1:
            cut = limit
        else:
            cut += 1
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def send_telegram_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")
    return payload


def main():
    if not BOT_TOKEN:
        print("ERROR: set TELEGRAM_BOT_TOKEN environment variable", file=sys.stderr)
        sys.exit(1)

    rows = load_rows()
    state = load_state()
    idx = state.get("next_index", 0)

    if idx >= len(rows):
        print("Все записи уже опубликованы — постить больше нечего.")
        return

    row = rows[idx]
    message = format_message(row)
    chunks = split_message(message)

    for i, chunk in enumerate(chunks):
        send_telegram_message(BOT_TOKEN, CHAT_ID, chunk)
        if i < len(chunks) - 1:
            time.sleep(1)  # be gentle with rate limits between parts of one entry

    state["next_index"] = idx + 1
    state["last_posted_post_id"] = row["post_id"]
    state["last_posted_date"] = row["date"]
    save_state(state)

    print(f"Опубликовано: post_id={row['post_id']} ({row['date']}), частей сообщения: {len(chunks)}")


if __name__ == "__main__":
    main()
