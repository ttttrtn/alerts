import os
import asyncio
import requests
from collections import deque
from flask import Flask, Response, request, send_from_directory
from lxml import html

# TikTok
from TikTokLive import TikTokLiveClient
from TikTokLive.events import FollowEvent, GiftEvent

# ================= CONFIG =================
TIKTOK_USERNAME = "joe363653"
POLL_INTERVAL = 6

TIDYLABS_URL = "https://tidylabs.stream/alertv3.asp?key=PMESLFPWKKB2K19I6I9B1740869846&tips=1&follow=1&subs=1&hosts=1&interactive=1"
NIMO_URL = "https://www.nimo.tv/vidwalla/alert-box?v=1&t=1773714076&id=1578570016&s=0243e7faef2e&_lang=1033"

MAX_QUEUE = 20
MAX_SEEN = 100

# ================= STATE =================
alert_queue = deque(maxlen=MAX_QUEUE)

seen_tidylabs = deque(maxlen=MAX_SEEN)
seen_nimo = deque(maxlen=MAX_SEEN)
seen_tiktok = deque(maxlen=MAX_SEEN)

# ================= FLASK =================
app = Flask(__name__)

@app.route("/overlay.html")
def overlay():
    return send_from_directory(".", "overlay.html")

@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory("static", path)

# 🔥 PUSH endpoint (for your local Rumble script)
@app.route("/push", methods=["POST"])
def push_alert():
    data = request.json
    if data and "message" in data:
        add_alert(data["message"], data.get("color", "white"))
    return {"status": "ok"}

# 🔥 REALTIME STREAM (NO POLLING)
@app.route("/stream")
def stream():
    def event_stream():
        last_id = 0
        while True:
            if alert_queue:
                alert = alert_queue.popleft()
                yield f"data: {alert}\n\n"
            asyncio.run(asyncio.sleep(0.5))

    return Response(event_stream(), mimetype="text/event-stream")

# ================= ALERT =================
def add_alert(msg, color="white"):
    alert_queue.append({
        "message": msg,
        "color": color
    })
    print(f"[ALERT] {msg}")

# ================= TIDYLABS =================
async def poll_tidylabs():
    while True:
        try:
            r = requests.get(TIDYLABS_URL, timeout=5)
            tree = html.fromstring(r.text)

            text = tree.xpath('//*[@id="alerttext"]/text()')
            if text:
                msg = text[0].strip()
                if msg and msg not in seen_tidylabs:
                    seen_tidylabs.append(msg)
                    add_alert(msg, "#00ffea")

        except Exception as e:
            print("[TIDYLABS ERROR]", e)

        await asyncio.sleep(POLL_INTERVAL)

# ================= NIMO =================
async def poll_nimo():
    while True:
        try:
            r = requests.get(NIMO_URL, timeout=5)
            tree = html.fromstring(r.text)

            text = tree.xpath('/html/body/div[1]/div/text()')
            if text:
                msg = text[0].strip()
                if msg and msg not in seen_nimo:
                    seen_nimo.append(msg)
                    add_alert(msg, "#00ffea")

        except Exception as e:
            print("[NIMO ERROR]", e)

        await asyncio.sleep(POLL_INTERVAL)

# ================= TIKTOK =================
class TikTokMonitor:
    def __init__(self, username):
        self.client = TikTokLiveClient(unique_id=username)
        self.seen = deque(maxlen=MAX_SEEN)

        self.client.on(FollowEvent)(self.on_follow)
        self.client.on(GiftEvent)(self.on_gift)

    async def on_follow(self, event):
        uid = f"{event.user.unique_id}"
        if uid in self.seen:
            return
        self.seen.append(uid)
        add_alert(f"{event.user.unique_id} followed!", "#00ffea")

    async def on_gift(self, event):
        uid = f"{event.user.unique_id}:{event.gift.gift_id}"
        if uid in self.seen:
            return
        self.seen.append(uid)
        add_alert(f"{event.user.unique_id} sent gift!", "#ffea00")

    async def run(self):
        while True:
            try:
                if not self.client.connected:
                    await self.client.connect()
                await asyncio.sleep(10)
            except Exception as e:
                print("[TikTok ERROR]", e)
                await asyncio.sleep(10)

# ================= START =================
async def main():
    asyncio.create_task(poll_tidylabs())
    asyncio.create_task(poll_nimo())

    tiktok = TikTokMonitor(TIKTOK_USERNAME)
    asyncio.create_task(tiktok.run())

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main())

    port = int(os.environ.get("PORT", 5000))
    print(f"🔥 Running optimized on {port}")

    threading = __import__("threading")
    threading.Thread(target=loop.run_forever, daemon=True).start()

    app.run(host="0.0.0.0", port=port)
