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
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/131 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()

        print("HTTP:", response.status)
        print("取得バイト数:", len(data))

        return data.decode("utf-8", errors="ignore")


def clean_text(text):
    text = unescape(text)
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_latest_gta_article():

    print("Newswireを取得中...")

    html = fetch(NEWSWIRE_URL)

    print("article URLの検索中...")

    # 日本語Newswireの記事URLを取得
    patterns = [
        r'href=["\'](/jp/newswire/article/[^"\']+)["\']',
        r'["\'](/jp/newswire/article/[^"\']+)["\']',
        r'(https://www\.rockstargames\.com/jp/newswire/article/[^"\']+)',
    ]

    urls = []

    for pattern in patterns:
        found = re.findall(pattern, html)

        for url in found:
            if url not in urls:
                urls.append(url)

    print("見つかった記事URL:", len(urls))

    if not urls:
        print("記事URLが見つかりませんでした。")
        print("Newswire HTMLに含まれる文字数:", len(html))

        # GTAオンラインという文字が存在するか確認
        if "GTAオンライン" in html:
            print("HTML内には「GTAオンライン」が存在します。")
        else:
            print("HTML内に「GTAオンライン」がありません。")

        return None

    for path in urls[:30]:

        if path.startswith("http"):
            url = path
        else:
            url = BASE_URL + path

        print("確認:", url)

        try:
            article_html = fetch(url)

            # GTAオンライン記事か確認
            if "GTAオンライン" not in article_html:
                print("→ GTAオンラインではありません")
                continue

            print("→ GTAオンライン記事です")

            # タイトル
            title = None

            patterns = [
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
                r'<title>(.*?)</title>',
            ]

            for pattern in patterns:
                match = re.search(
                    pattern,
                    article_html,
                    re.IGNORECASE | re.DOTALL,
                )

                if match:
                    title = clean_text(match.group(1))
                    break

            if not title:
                title = "GTAオンライン 新着ニュース"

            # 説明
            description = (
                "Rockstar Games Newswireで "
                "GTAオンラインの新しい記事が公開されました。"
            )

            description_patterns = [
                r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
            ]

            for pattern in description_patterns:
                match = re.search(
                    pattern,
                    article_html,
                    re.IGNORECASE | re.DOTALL,
                )

                if match:
                    description = clean_text(match.group(1))
                    break

            # 画像
            image = None

            image_patterns = [
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            ]

            for pattern in image_patterns:
                match = re.search(
                    pattern,
                    article_html,
                    re.IGNORECASE,
                )

                if match:
                    image = match.group(1)
                    break

            return {
                "url": url,
                "title": title,
                "description": description,
                "image": image,
            }

        except Exception as error:
            print("記事取得エラー:", error)

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
            {
                "last_url": url
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def send_to_discord(article):

    embed = {
        "title": article["title"],
        "url": article["url"],
        "description": article["description"],
        "color": 0xE67E22,
        "footer": {
            "text": "Rockstar Games Newswire",
        },
    }

    if article["image"]:
        embed["image"] = {
            "url": article["image"]
        }

    payload = {
        "username": "GTA NEWS",
        "embeds": [embed],
    }

    data = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "GTA-News-Discord-Bot",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        print("Discord HTTP:", response.status)


def main():

    print("=== GTA NEWS BOT START ===")

    article = get_latest_gta_article()

    if not article:
        print("GTAオンラインの記事を取得できませんでした。")
        return

    print("最新記事:")
    print(article["title"])
    print(article["url"])

    last_url = load_state()

    if last_url is None:

        save_state(article["url"])

        print("初回実行です。")
        print("現在の記事を記録しました。")
        print("Discordへの投稿は行いません。")

        return

    if article["url"] == last_url:

        print("新しい記事はありません。")

        return

    print("新しい記事を検出しました！")

    send_to_discord(article)

    save_state(article["url"])

    print("Discordへの投稿完了！")


if __name__ == "__main__":
    main()
