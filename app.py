# overlay_queue.py
import os
import threading
import time
import requests
from collections import deque
from lxml import html
import asyncio
import socket

from flask import Flask, jsonify, send_from_directory
from TikTokLive import TikTokLiveClient
from TikTokLive.events import FollowEvent, GiftEvent, ConnectEvent

# ================= CONFIG =================
RUMBLE_API_URL = (
    "https://rumble.com/-livestream-api/get-data"
    "?key=eOTcfDFLJczJlogKGFsGa77bhhc8sfBnIOOQyd8Kwu2bDE642Kdhh3j61dVFMtU7rhp5gNG_MSruuMrLN2XT0w"
)
TIDYLABS_URL = "https://tidylabs.stream/alertv3.asp?key=PMESLFPWKKB2K19I6I9B1740869846&tips=1&follow=1&subs=1&hosts=1&interactive=1"
NIMO_URL = "https://www.nimo.tv/vidwalla/alert-box?v=1&t=1773714076&id=1578570016&s=0243e7faef2e&_lang=1033"
TIKTOK_USERNAME = "joe363653"
POLL_INTERVAL = 2

# ================= STATE =================
alert_queue = deque()
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

@app.route("/overlay.html")
def overlay_html():
    return send_from_directory(".", "overlay.html")

@app.route("/static/<path:file>")
def static_files(file):
    return send_from_directory("./static", file)

def add_alert(msg, color="white"):
    alert_queue.append({"message": msg, "color": color})

# ================= POLLERS =================
def poll_rumble():
    while True:
        try:
            r = requests.get(RUMBLE_API_URL, timeout=10)
            r.raise_for_status()
            data = r.json()
            items = data.get("followers", {}).get("recent_followers", [])
            if data.get("followers", {}).get("latest_follower"):
                items.append(data["followers"]["latest_follower"])
            for f in items:
                eid = f"follow:{f['username']}:{f['followed_on']}"
                if eid not in seen_rumble:
                    seen_rumble.add(eid)
                    add_alert(f"{f['username']} just followed!", color="#00ffea")
        except Exception as e:
            print(f"[RUMBLE ERROR] {e}")
        time.sleep(POLL_INTERVAL)

def poll_tidylabs():
    while True:
        try:
            r = requests.get(TIDYLABS_URL, timeout=10)
            r.raise_for_status()
            tree = html.fromstring(r.text)
            text = tree.xpath('//*[@id="alerttext"]/text()')
            if text:
                text = text[0].strip()
                if text and text not in seen_tidylabs:
                    seen_tidylabs.add(text)
                    add_alert(text, color="#00ffea")
        except Exception as e:
            print(f"[TIDYLABS ERROR] {e}")
        time.sleep(POLL_INTERVAL)

def poll_nimo():
    while True:
        try:
            r = requests.get(NIMO_URL, timeout=10)
            r.raise_for_status()
            tree = html.fromstring(r.text)
            text = tree.xpath('/html/body/div[1]/div/text()')
            if text:
                text = text[0].strip()
                if text and text not in seen_nimo:
                    seen_nimo.add(text)
                    add_alert(text, color="#00ffea")
        except Exception as e:
            print(f"[NIMO ERROR] {e}")
        time.sleep(POLL_INTERVAL)

# ================= TIKTOK =================
class TikTokMonitor:
    def __init__(self, username):
        self.username = username
        self.client = TikTokLiveClient(unique_id=username)
        self.client.on(FollowEvent)(self.on_follow)
        self.client.on(GiftEvent)(self.on_gift)
        self.client.on(ConnectEvent)(self.on_connect)
        self.seen = set()

    async def on_connect(self, event):
        print(f"[TikTok Connected] @{self.username}")

    async def on_follow(self, event: FollowEvent):
        uid = f"tiktok_follow:{event.user.unique_id}"
        if uid in self.seen: return
        self.seen.add(uid)
        add_alert(f"{event.user.unique_id} just followed!", color="#00ffea")
        print(f"[TikTok] {event.user.unique_id} followed!")

    async def on_gift(self, event: GiftEvent):
        uid = f"tiktok_gift:{event.user.unique_id}:{event.gift.gift_id}"
        if uid in self.seen: return
        self.seen.add(uid)
        add_alert(f"{event.user.unique_id} sent a gift!", color="#ffea00")
        print(f"[TikTok] {event.user.unique_id} sent a gift!")

    async def monitor(self):
        while True:
            try:
                if not self.client.connected:
                    await self.client.connect()
                await asyncio.sleep(5)
            except Exception as e:
                print(f"[TikTok ERROR] {e}")
                if self.client.connected:
                    await self.client.disconnect()
                await asyncio.sleep(5)

# ================= UTIL =================
def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

# ================= START =================
if __name__ == "__main__":
    # Start pollers
    threading.Thread(target=poll_rumble, daemon=True).start()
    threading.Thread(target=poll_tidylabs, daemon=True).start()
    threading.Thread(target=poll_nimo, daemon=True).start()

    # Start TikTok monitor
    monitor = TikTokMonitor(TIKTOK_USERNAME)
    asyncio.get_event_loop().create_task(monitor.monitor())

    # LAN info
    lan_ip = get_lan_ip()
    print(f"🔥 Overlay running on LAN: http://{lan_ip}:5000/overlay.html")

    # Run Flask using Render's port
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
