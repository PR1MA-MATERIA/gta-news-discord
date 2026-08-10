```python
import os
import json
import urllib.request
import urllib.parse
from pathlib import Path

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

GRAPHQL_URL = "https://graph.rockstargames.com"
BASE_URL = "https://www.rockstargames.com"

STATE_FILE = Path("last_posted.json")

# GTA Online / GTA V 系のNewswireタグ
# 既存のRockstar Newswire実装で使用されているID
GTA_V_TAG_ID = 702


def graphql_request(query_params):
    url = GRAPHQL_URL + "?" + urllib.parse.urlencode(query_params)

    request = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/131 Safari/537.36"
            ),
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()

        print("GraphQL HTTP:", response.status)
        print("取得バイト数:", len(data))

        return json.loads(data.decode("utf-8", errors="ignore"))


def get_hash_token():
    """
    Rockstar NewswireのGraphQL Persisted Query用ハッシュを取得します。

    現在のNewswireはブラウザ側からGraphQLの
    NewswireListクエリを呼び出して記事一覧を取得しています。
    """

    # 現時点では固定ハッシュを使用せず、
    # まずGraphQL APIが直接応答するかを確認します。
    return None


def get_latest_gta_article():
    print("Rockstar Newswireを確認中...")

    # まず現在のGraphQL APIにアクセス
    variables = {
        "page": 1,
        "tagId": GTA_V_TAG_ID,
        "metaUrl": "/newswire",
        "locale": "ja_jp",
    }

    params = {
        "operationName": "NewswireList",
        "variables": json.dumps(
            variables,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }

    print("GraphQLへ接続中...")

    try:
        response = graphql_request(params)

    except Exception as error:
        print("GraphQL取得エラー:", error)
        return None

    print("GraphQLレスポンスを解析中...")

    if response.get("errors"):
        print("GraphQL errors:")
        print(json.dumps(
            response["errors"],
            ensure_ascii=False,
            indent=2,
        ))

        return None

    data = response.get("data")

    if not data:
        print("GraphQL dataがありません。")
        print(json.dumps(
            response,
            ensure_ascii=False,
            indent=2,
        ))

        return None

    posts = data.get("posts", {})
    results = posts.get("results", [])

    print("取得記事数:", len(results))

    if not results:
        print("記事が見つかりませんでした。")
        return None

    article = results[0]

    article_id = article.get("id")
    title = article.get("title")
    relative_url = article.get("url")
    created = article.get("created")

    if not relative_url:
        print("記事URLがありません。")
        return None

    if relative_url.startswith("http"):
        article_url = relative_url
    else:
        article_url = BASE_URL + relative_url

    preview = article.get("preview_images_parsed", {})
    newswire_block = preview.get("newswire_block", {})
    image = newswire_block.get("d16x9")

    primary_tags = article.get("primary_tags", [])

    tags = []

    for tag in primary_tags:
        name = tag.get("name")

        if name:
            tags.append(name)

    print("最新記事:")
    print("ID:", article_id)
    print("タイトル:", title)
    print("URL:", article_url)
    print("タグ:", tags)

    return {
        "id": str(article_id),
        "url": article_url,
        "title": title or "GTA Online 新着ニュース",
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
    description = ""

    if article["tags"]:
        description = " ".join(
            f"`{tag}`"
            for tag in article["tags"]
        )

    embed = {
        "author": {
            "name": "Rockstar Games Newswire",
            "url": "https://www.rockstargames.com/jp/newswire",
        },
        "title": article["title"],
        "url": article["url"],
        "description": description,
        "color": 0xE67E22,
        "footer": {
            "text": "Rockstar Games Newswire",
        },
    }

    if article.get("image"):
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

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        print(
            "Discord HTTP:",
            response.status
        )


def main():
    print("=== GTA NEWS BOT START ===")

    article = get_latest_gta_article()

    if not article:
        print("GTA Onlineの記事を取得できませんでした。")
        return

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
```
