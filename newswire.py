import os
import re
import json
import urllib.request
from pathlib import Path
from html import unescape

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

NEWSWIRE_URL = "https://www.rockstargames.com/jp/newswire"
BASE_URL = "https://www.rockstargames.com"

STATE_FILE = Path("last_posted.json")


def fetch(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 GTA-News-Discord-Bot"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def clean_text(text):
    text = unescape(text)
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_latest_gta_article():
    html = fetch(NEWSWIRE_URL)

    # Newswireの記事URLを取得
    pattern = r'href=["\'](/jp/newswire/article/[^"\']+)["\']'
    urls = re.findall(pattern, html)

    # 重複削除
    urls = list(dict.fromkeys(urls))

    for path in urls[:30]:
        url = BASE_URL + path

        try:
            article_html = fetch(url)

            # GTAオンラインの記事だけを対象にする
            if "GTAオンライン" not in article_html:
                continue

            # タイトルを取得
            title_match = re.search(
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                article_html,
                re.IGNORECASE
            )

            if not title_match:
                title_match = re.search(
                    r'<title>(.*?)</title>',
                    article_html,
                    re.IGNORECASE | re.DOTALL
                )

            title = (
                clean_text(title_match.group(1))
                if title_match
                else "GTAオンライン 新着ニュース"
            )

            # 説明文を取得
            description_match = re.search(
                r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',
                article_html,
                re.IGNORECASE
            )

            description = (
                clean_text(description_match.group(1))
                if description_match
                else "Rockstar Games Newswireで新しい記事が公開されました。"
            )

            # サムネイル取得
            image_match = re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                article_html,
                re.IGNORECASE
            )

            image = image_match.group(1) if image_match else None

            return {
                "url": url,
                "title": title,
                "description": description,
                "image": image,
            }

        except Exception as error:
            print(f"記事取得エラー: {url}")
            print(error)

    return None


def load_state():
    if not STATE_FILE.exists():
        return None

    try:
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
        return data.get("last_url")
    except Exception:
        return None


def save_state(url):
    STATE_FILE.write_text(
        json.dumps(
            {"last_url": url},
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def send_to_discord(article):
    embed = {
        "title": article["title"],
        "url": article["url"],
        "description": article["description"],
        "color": 0xE67E22,
        "footer": {
            "text": "Rockstar Games Newswire"
        }
    }

    if article["image"]:
        embed["image"] = {
            "url": article["image"]
        }

    payload = {
        "username": "GTA NEWS",
        "embeds": [embed]
    }

    data = json.dumps(
        payload,
        ensure_ascii=False
    ).encode("utf-8")

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
        print("Discord:", response.status)


def main():
    print("Newswireを確認しています...")

    article = get_latest_gta_article()

    if not article:
        print("GTAオンラインの記事が見つかりませんでした。")
        return

    print("最新記事:")
    print(article["title"])
    print(article["url"])

    last_url = load_state()

    # 初回は現在の記事を記録するだけ
    if last_url is None:
        save_state(article["url"])
        print("初回実行なので投稿せず、記事を記録しました。")
        return

    # 同じ記事なら何もしない
    if article["url"] == last_url:
        print("新しい記事はありません。")
        return

    # 新記事
    send_to_discord(article)
    save_state(article["url"])

    print("新しい記事をDiscordへ投稿しました。")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
