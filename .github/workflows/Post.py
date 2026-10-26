
 
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import logging
from html import escape
import feedparser
import requests

CONFIG_FILE = "config.json"
POSTED_FILE = "posted_urls.json"
SLEEP_BETWEEN_SENDS = 1  # секунды


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN или CHAT_ID не заданы в окружении")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def format_entry(entry):
    title = escape(entry.get("title", "Без названия"))
    link = entry.get("link", "")
    # summary может быть HTML — экранируем его, чтобы Telegram корректно показал
    summary = escape(entry.get("summary", "") or entry.get("description", "") or "")
    # Ограничим длину summary (чтобы сообщение не было слишком большим)
    if len(summary) > 800:
        summary = summary[:800].rsplit(" ", 1)[0] + "…"

    msg_parts = []
    msg_parts.append(f"<b>{title}</b>")
    if summary:
        msg_parts.append(summary)
    if link:
        msg_parts.append(link)

    return "\n\n".join(msg_parts)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    config = load_json(CONFIG_FILE, {})
    feeds = config.get("feeds", [])
    if not feeds:
        logging.error("В файле config.json нет поля 'feeds' или список пуст.")
        return

    posted = load_json(POSTED_FILE, [])
    if not isinstance(posted, list):
        posted = []
    posted_set = set(posted)

    for feed_url in feeds:
        logging.info("Парсим фид: %s", feed_url)
        try:
            d = feedparser.parse(feed_url)
        except Exception as e:
            logging.error("Ошибка при парсинге %s: %s", feed_url, e)
            continue

        entries = d.entries or []
        # Можно сортировать по published_parsed, если оно есть
        try:
            entries.sort(key=lambda e: e.get("published_parsed") or 0)
        except Exception:
            pass

        for entry in entries:
            link = entry.get("link", "")
            if not link:
                continue
            if link in posted_set:
                continue

            try:
                text = format_entry(entry)
                logging.info("Отправляю: %s", link)
                send_telegram(text)
                # Добавляем в список отправленных и сохраняем
                posted.append(link)
                posted_set.add(link)
                save_json(POSTED_FILE, posted)
                time.sleep(SLEEP_BETWEEN_SENDS)
            except requests.HTTPError as he:
                logging.error("HTTP ошибка при отправке в Telegram: %s", he)
            except Exception as ex:
                logging.error("Ошибка при обработке записи %s: %s", link, ex)


if __name__ == "__main__":
    main()
 
