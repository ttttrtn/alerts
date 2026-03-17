# overlay_queue.py
import os
import threading
import time
import requests
from collections import deque
from lxml import html
import asyncio

from flask import Flask, jsonify, send_from_directory

# TikTok
from TikTokLive import TikTokLiveClient
from TikTokLive.events import FollowEvent, GiftEvent, ConnectEvent

# ================= CONFIG =================
RUMBLE_API_URL = "https://rumble.com/-livestream-api/get-data?key=eOTcfDFLJczJlogKGFsGa77bhhc8sfBnIOOQyd8Kwu2bDE642Kdhh3j61dVFMtU7rhp5gNG_MSruuMrLN2XT0w"
TIDYLABS_URL = "https://tidylabs.stream/alertv3.asp?key=PMESLFPWKKB2K19I6I9B1740869846&tips=1&follow=1&subs=1&hosts=1&interactive=1"
NIMO_URL = "https://www.nimo.tv/vidwalla/alert-box?v=1&t=1773714076&id=1578570016&s=0243e7faef2e&_lang=1033"

TIKTOK_USERNAME = "joe363653"
POLL_INTERVAL = 3  # slower for Render free tier

# ================= STATE =================
alert_queue = deque(maxlen=50)

seen_rumble = set()
seen_tidylabs = set()
seen_nimo = set()
seen_tiktok = set()

# ================= FLASK =================
app = Flask(__name__)

@app.route("/latest")
def latest():
    if alert_queue:
        return jsonify(alert_queue.popleft())
    return jsonify({"message": ""})

from flask import request

@app.route("/push", methods=["POST"])
def push_alert():
    data = request.json
    print("[PUSH RECEIVED]", data)  # 👈 IMPORTANT DEBUG

    if data and "message" in data:
        add_alert(data["message"], data.get("color", "white"))

    return {"status": "ok"}

@app.route("/overlay.html")
def overlay():
    return send_from_directory(".", "overlay.html")

@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory("static", path)

def add_alert(msg, color="white"):
    alert_queue.append({
        "message": msg,
        "color": color
    })
    print(f"[ALERT] {msg}")

# ================= RUMBLE =================
def poll_rumble():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    while True:
        try:
            r = requests.get(RUMBLE_API_URL, headers=headers, timeout=10)
            if r.status_code == 403:
                print("[RUMBLE] 403 blocked (skipping)")
                time.sleep(10)
                continue

            data = r.json()

            followers = data.get("followers", {})
            items = followers.get("recent_followers", [])

            if followers.get("latest_follower"):
                items.append(followers["latest_follower"])

            for f in items:
                eid = f"follow:{f['username']}:{f['followed_on']}"
                if eid not in seen_rumble:
                    seen_rumble.add(eid)
                    add_alert(f"{f['username']} just followed!", "#00ffea")

        except Exception as e:
            print(f"[RUMBLE ERROR] {e}")

        time.sleep(POLL_INTERVAL)

# ================= TIDYLABS =================
def poll_tidylabs():
    while True:
        try:
            r = requests.get(TIDYLABS_URL, timeout=10)
            tree = html.fromstring(r.text)

            text = tree.xpath('//*[@id="alerttext"]/text()')

            if text:
                msg = text[0].strip()
                if msg and msg not in seen_tidylabs:
                    seen_tidylabs.add(msg)
                    add_alert(msg, "#00ffea")

        except Exception as e:
            print(f"[TIDYLABS ERROR] {e}")

        time.sleep(POLL_INTERVAL)

# ================= NIMO =================
def poll_nimo():
    while True:
        try:
            r = requests.get(NIMO_URL, timeout=10)
            tree = html.fromstring(r.text)

            text = tree.xpath('/html/body/div[1]/div/text()')

            if text:
                msg = text[0].strip()
                if msg and msg not in seen_nimo:
                    seen_nimo.add(msg)
                    add_alert(msg, "#00ffea")

        except Exception as e:
            print(f"[NIMO ERROR] {e}")

        time.sleep(POLL_INTERVAL)

# ================= TIKTOK =================
class TikTokMonitor:
    def __init__(self, username):
        self.client = TikTokLiveClient(unique_id=username)
        self.seen = set()

        self.client.on(FollowEvent)(self.on_follow)
        self.client.on(GiftEvent)(self.on_gift)
        self.client.on(ConnectEvent)(self.on_connect)

    async def on_connect(self, event):
        print("[TikTok] Connected")

    async def on_follow(self, event: FollowEvent):
        uid = f"follow:{event.user.unique_id}"
        if uid in self.seen:
            return

        self.seen.add(uid)
        add_alert(f"{event.user.unique_id} just followed!", "#00ffea")

    async def on_gift(self, event: GiftEvent):
        uid = f"gift:{event.user.unique_id}:{event.gift.gift_id}"
        if uid in self.seen:
            return

        self.seen.add(uid)
        add_alert(f"{event.user.unique_id} sent a gift!", "#ffea00")

    async def run(self):
        while True:
            try:
                if not self.client.connected:
                    await self.client.connect()
                await asyncio.sleep(5)
            except Exception as e:
                print(f"[TikTok ERROR] {e}")
                try:
                    await self.client.disconnect()
                except:
                    pass
                await asyncio.sleep(5)

# ================= START =================
if __name__ == "__main__":
    # Start polling threads
    threading.Thread(target=poll_rumble, daemon=True).start()
    threading.Thread(target=poll_tidylabs, daemon=True).start()
    threading.Thread(target=poll_nimo, daemon=True).start()

    # Start TikTok (FIXED EVENT LOOP)
    monitor = TikTokMonitor(TIKTOK_USERNAME)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(monitor.run())

    threading.Thread(target=loop.run_forever, daemon=True).start()

    # Start Flask (Render compatible)
    port = int(os.environ.get("PORT", 5000))
    print(f"🔥 Running on port {port}")

    app.run(host="0.0.0.0", port=port)
