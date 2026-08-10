import os
import json
import re
import urllib.request
from html import unescape
from pathlib import Path

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

NEWSWIRE_URL = "https://www.rockstargames.com/jp/newswire"

STATE_FILE = Path("last_posted.json")


def fetch_page(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 GTA-News-Discord-Bot"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def clean_html(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_news(html):
    """
    Rockstar NewswireのHTMLから記事らしいURLを探します。
    """
    pattern = r'href="(/jp/newswire/article/[^"]+)"'
    urls = re.findall(pattern, html)

    # 重複除去
    result = []

    for url in urls:
        if url not in result:
            result.append(url)

    return result


def load_state():
    if not STATE_FILE.exists():
        return None

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data.get("last_url")
    except Exception:
        return None


def save_state(url):
    STATE_FILE.write_text(
        json.dumps({"last_url": url}, ensure_ascii=False),
        encoding="utf-8"
    )


def send_discord(title, url):
    payload = {
        "username": "GTA NEWS",
        "embeds": [
            {
                "title": title,
                "url": url,
                "description": "Rockstar Games Newswireで新しい記事が公開されました。",
                "color": 0xFFAA00,
                "footer": {
                    "text": "Rockstar Games Newswire"
                }
            }
        ]
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "GTA-News-Discord-Bot"
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        print("Discord response:", response.status)


def main():
    html = fetch_page(NEWSWIRE_URL)

    news = find_news(html)

    if not news:
        print("記事が見つかりませんでした。")
        return

    # Newswireページの先頭記事
    latest_url = "https://www.rockstargames.com" + news[0]

    last_url = load_state()

    # 初回実行時は投稿せず、現在の記事を記録
    if last_url is None:
        save_state(latest_url)
        print("初回実行：最新記事を記録しました。")
        return

    # 新記事がなければ終了
    if latest_url == last_url:
        print("新しい記事はありません。")
        return

    # 仮タイトル
    title = "GTA Online 新着ニュース"

    send_discord(title, latest_url)

    save_state(latest_url)

    print("新しい記事をDiscordへ投稿しました。")


if __name__ == "__main__":
    main()
