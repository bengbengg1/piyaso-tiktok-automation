"""Read-only Buffer API connection and TikTok channel verification.

No mutation is sent and no post is created. Use `--check` in GitHub Actions
before rendering, so missing/incorrect credentials fail before expensive work.
"""
from __future__ import annotations

import argparse
import json
import os
from urllib.request import Request, urlopen

from publish import BUFFER_API, required


def query_buffer(query, variables=None, *, opener=urlopen):
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = Request(BUFFER_API, data=payload, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + required("BUFFER_API_KEY"),
    })
    with opener(request, timeout=35) as response:
        answer = json.loads(response.read())
    if answer.get("errors"):
        # Do not include request headers/API keys in messages.
        raise RuntimeError("Buffer GraphQL sorgusu reddedildi: " + str(answer["errors"])[:500])
    return answer.get("data") or {}


def list_channels(query_fn=None):
    query_fn = query_fn or query_buffer
    data = query_fn("query { account { organizations { id name } } }")
    result = []
    for org in (data.get("account") or {}).get("organizations") or []:
        # GraphQL string escaping; this is an org ID from Buffer itself.
        org_id = json.dumps(org["id"])
        query = "query { channels(input: {organizationId: " + org_id + "}) { id name service isQueuePaused } }"
        rows = query_fn(query).get("channels") or []
        for row in rows:
            result.append({"organization": org.get("name", ""), **row})
    return result


def validate_tiktok_channel(channel_id, channels):
    if not channel_id:
        raise RuntimeError("BUFFER_CHANNEL_ID eksik. Listelenen TikTok channelId'yi GitHub Secret olarak girin.")
    found = next((c for c in channels if c.get("id") == channel_id), None)
    if not found:
        raise RuntimeError("BUFFER_CHANNEL_ID bu Buffer hesabındaki kanallarla uyuşmuyor.")
    if str(found.get("service", "")).lower() != "tiktok":
        raise RuntimeError("Bu channelId TikTok'a ait değil; yanlış sosyal ağa otomatik yayın engellendi.")
    if found.get("isQueuePaused") is True:
        raise RuntimeError("TikTok Buffer yayın kuyruğu duraklatılmış. Buffer'da açın.")
    return found


def main():
    parser = argparse.ArgumentParser(description="Buffer hesabını salt-okunur doğrula; gönderi oluşturmaz.")
    parser.add_argument("--check", action="store_true", help="BUFFER_CHANNEL_ID TikTok için doğru mu kontrol et")
    args = parser.parse_args()
    channels = list_channels()
    if args.check:
        selected = validate_tiktok_channel(os.getenv("BUFFER_CHANNEL_ID", "").strip(), channels)
        print("BAĞLANTI DOĞRULANDI (salt okunur): TikTok kanal = " + selected.get("name", "TikTok"))
        print("Hiçbir video yüklenmedi; hiçbir gönderi planlanmadı.")
    else:
        if not channels:
            print("Buffer hesabında bağlı sosyal kanal bulunamadı. Önce Buffer'dan TikTok bağlayın.")
        for ch in channels:
            print(f"{ch.get('service')} | {ch.get('name')} | channelId={ch.get('id')}")


if __name__ == "__main__":
    main()
