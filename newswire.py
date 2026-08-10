import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

NEWSWIRE_URL = "https://www.rockstargames.com/jp/newswire"
GRAPHQL_URL = "https://graph.rockstargames.com"

STATE_FILE = Path("last_posted.json")

# Rockstar NewswireのGTA V / GTA Onlineカテゴリ
GTA_V_TAG_ID = 702


def get_news_hash():
    """
    Rockstar NewswireをChromiumで開き、
    NewswireList GraphQLリクエストから
    Persisted Queryのsha256Hashを取得する。
    """

    print("Newswireをブラウザで開いてGraphQLハッシュを取得中...")

    captured_hash = None

    with sync_playwright() as playwright:

        browser = playwright.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        def handle_request(route):
            nonlocal captured_hash

            request = route.request
            url = request.url

            if "graph.rockstargames.com" in url and "operationName=NewswireList" in url:

                print("NewswireListリクエストを検出しました。")

                try:
                    parsed = urllib.parse.urlparse(url)

                    query = urllib.parse.parse_qs(
                        parsed.query
                    )

                    extensions_raw = query.get(
                        "extensions",
                        [None]
                    )[0]

                    if extensions_raw:

                        extensions = json.loads(
                            extensions_raw
                        )

                        persisted_query = extensions.get(
                            "persistedQuery",
                            {}
                        )

                        captured_hash = persisted_query.get(
                            "sha256Hash"
                        )

                        if captured_hash:
                            print(
                                "GraphQL hash取得成功:",
                                captured_hash
                            )

                            # ハッシュだけ取得できれば、
                            # このリクエスト自体は不要。
                            route.abort()
                            return

                except Exception as error:
                    print(
                        "GraphQLハッシュ解析エラー:",
                        error
                    )

            route.continue_()

        page.route(
            "**/*",
            handle_request
        )

        try:
            page.goto(
                NEWSWIRE_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            # JavaScriptがNewswireListを発行するまで待つ
            page.wait_for_timeout(15000)

        except PlaywrightTimeoutError:
            print(
                "Newswireの読み込みがタイムアウトしました。"
            )

        except Exception as error:
            print(
                "Newswireブラウザ取得エラー:",
                error
            )

        finally:
            browser.close()

    if not captured_hash:
        print(
            "GraphQL hashを取得できませんでした。"
        )

    return captured_hash


def graphql_request(news_hash):
    """
    Rockstar GraphQL APIからNewswire一覧を取得する。
    """

    variables = {
        "page": 1,
        "tagId": GTA_V_TAG_ID,
        "metaUrl": "/newswire",
        "locale": "ja_jp",
    }

    extensions = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": news_hash,
        }
    }

    params = urllib.parse.urlencode(
        {
            "operationName": "NewswireList",
            "variables": json.dumps(
                variables,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "extensions": json.dumps(
                extensions,
                separators=(",", ":"),
            ),
        }
    )

    url = GRAPHQL_URL + "?" + params

    print("Rockstar GraphQL APIへ接続中...")

    request = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/131 Safari/537.36"
            ),
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        data = response.read()

        print(
            "GraphQL HTTP:",
            response.status
        )

        print(
            "取得バイト数:",
            len(data)
        )

        return json.loads(
            data.decode(
                "utf-8",
                errors="ignore"
            )
        )


def get_latest_article():
    """
    最新のGTA Online / GTA V Newswire記事を取得する。
    """

    news_hash = get_news_hash()

    if not news_hash:
        return None

    try:
        response = graphql_request(
            news_hash
        )

    except Exception as error:
        print(
            "GraphQL取得エラー:",
            error
        )

        return None

    # PersistedQueryNotFoundの場合は
    # hashが変更された可能性がある。
    if response.get("errors"):

        print(
            "GraphQL errors:"
        )

        print(
            json.dumps(
                response["errors"],
                ensure_ascii=False,
                indent=2
            )
        )

        return None

    data = response.get("data")

    if not data:
        print(
            "GraphQLのdataがありません。"
        )

        return None

    posts = data.get(
        "posts",
        {}
    )

    results = posts.get(
        "results",
        []
    )

    print(
        "取得記事数:",
        len(results)
    )

    if not results:
        print(
            "Newswire記事が見つかりませんでした。"
        )

        return None

    article = results[0]

    article_id = article.get(
        "id"
    )

    title = article.get(
        "title"
    )

    relative_url = article.get(
        "url"
    )

    created = article.get(
        "created"
    )

    if not relative_url:
        print(
            "記事URLがありません。"
        )

        return None

    if relative_url.startswith(
        "http"
    ):
        article_url = relative_url

    else:
        article_url = (
            "https://www.rockstargames.com"
            + relative_url
        )

    # Newswire用16:9画像
    image = None

    preview_images = article.get(
        "preview_images_parsed",
        {}
    )

    newswire_block = preview_images.get(
        "newswire_block",
        {}
    )

    image = newswire_block.get(
        "d16x9"
    )

    # タグ
    tags = []

    for tag in article.get(
        "primary_tags",
        []
    ):

        tag_name = tag.get(
            "name"
        )

        if tag_name:
            tags.append(
                tag_name
            )

    print()
    print("===== 最新記事 =====")
    print("ID:", article_id)
    print("タイトル:", title)
    print("URL:", article_url)
    print("公開日時:", created)
    print("タグ:", tags)
    print("画像:", image)
    print("====================")
    print()

    return {
        "id": str(article_id),
        "title": title or "GTA Newswire",
        "url": article_url,
        "image": image,
        "date": created,
        "tags": tags,
    }


def load_state():
    if not STATE_FILE.exists():
        return None

    try:
        data = json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        return data.get(
            "last_url"
        )

    except Exception as error:
        print(
            "状態ファイル読み込みエラー:",
            error
        )

        return None


def save_state(url):
    STATE_FILE.write_text(
        json.dumps(
            {
                "last_url": url
            },
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def send_to_discord(article):
    """
    Discord WebhookへNewswire風Embedを送信。
    """

    tags_text = ""

    if article["tags"]:
        tags_text = " ".join(
            f"`{tag}`"
            for tag in article["tags"]
        )

    embed = {
        "author": {
            "name": "Rockstar Games Newswire",
            "url": NEWSWIRE_URL,
        },

        "title": article["title"],

        "url": article["url"],

        "description": tags_text,

        "color": 0xE67E22,

        "footer": {
            "text": "Rockstar Games Newswire"
        }
    }

    if article.get("image"):
        embed["image"] = {
            "url": article["image"]
        }

    payload = {
        "username": "GTA NEWS",
        "embeds": [
            embed
        ]
    }

    data = json.dumps(
        payload,
        ensure_ascii=False
    ).encode(
        "utf-8"
    )

    request = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "GTA-News-Discord-Bot",
        },
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        print(
            "Discord HTTP:",
            response.status
        )


def main():

    print(
        "=== GTA NEWS BOT START ==="
    )

    article = get_latest_article()

    if not article:

        print(
            "GTA Newswireの記事を取得できませんでした。"
        )

        return

    last_url = load_state()

    # 初回実行
    if last_url is None:

        save_state(
            article["url"]
        )

        print(
            "初回実行です。"
        )

        print(
            "現在の最新記事を記録しました。"
        )

        print(
            "Discordへの投稿は行いません。"
        )

        return

    # 同じ記事
    if article["url"] == last_url:

        print(
            "新しい記事はありません。"
        )

        return

    # 新記事
    print(
        "新しい記事を検出しました！"
    )

    send_to_discord(
        article
    )

    save_state(
        article["url"]
    )

    print(
        "Discordへの投稿完了！"
    )


if __name__ == "__main__":
    main()

