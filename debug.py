import urllib.request

url = "https://www.rockstargames.com/jp/newswire"

request = urllib.request.Request(
    url,
    headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
    },
)

with urllib.request.urlopen(request, timeout=30) as response:
    data = response.read()

print("HTTP:", response.status)
print("SIZE:", len(data))

with open("rockstar.html", "wb") as f:
    f.write(data)

print("rockstar.htmlを保存しました")
