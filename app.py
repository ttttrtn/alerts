from flask import Flask, jsonify
from collections import deque
import requests
import time
import threading

# ========== CONFIG ==========
RUMBLE_API_URL = (
    "https://rumble.com/-livestream-api/get-data"
    "?key=eOTcfDFLJczJlogKGFsGa77bhhc8sfBnIOOQyd8Kwu2bDE642Kdhh3j61dVFMtU7rhp5gNG_MSruuMrLN2XT0w"
)
POLL_INTERVAL = 2

# ========== STATE ==========
alerts = deque()
seen_events = set()

# ========== FLASK ==========
app = Flask(__name__)

@app.route("/latest")
def latest():
    if alerts:
        return jsonify(alerts.popleft())
    return jsonify({"message": ""})

def add_alert(message, color="white"):
    alerts.append({"message": message, "color": color})

# ========== EVENT PARSERS ==========
def process_event(event_id, alert_type, user, amount=None):
    if event_id in seen_events:
        return
    seen_events.add(event_id)
    if alert_type == "follow":
        add_alert(f"{user} just followed!", color="#00ffea")
    elif alert_type == "donation":
        add_alert(f"{user} donated ${amount}!", color="#ffea00")
    elif alert_type == "sub":
        add_alert(f"{user} subscribed!", color="#ff4d4d")
    else:
        add_alert(f"{user} triggered {alert_type}", color="white")

def parse_followers(data):
    section = data.get("followers", {})
    items = section.get("recent_followers", [])
    if section.get("latest_follower"):
        items.append(section["latest_follower"])
    for f in items:
        eid = f"follow:{f['username']}:{f['followed_on']}"
        process_event(eid, "follow", f['username'])

def parse_subscribers(data):
    section = data.get("subscribers", {})
    items = section.get("recent_subscribers", [])
    if section.get("latest_subscriber"):
        items.append(section["latest_subscriber"])
    for s in items:
        eid = f"sub:{s['username']}:{s['subscribed_on']}"
        process_event(eid, "sub", s['username'])

def parse_gifted_subs(data):
    section = data.get("gifted_subs", {})
    items = section.get("recent_gifted_subs", [])
    if section.get("latest_gifted_sub"):
        items.append(section["latest_gifted_sub"])
    for g in items:
        user = g.get("purchased_by", "Anonymous")
        eid = f"gift:{user}:{g.get('total_gifts')}:{g.get('video_id')}"
        process_event(eid, "sub", user)

def parse_chat_and_rants(chat):
    if not chat:
        return
    rants = chat.get("recent_rants", [])
    if chat.get("latest_rant"):
        rants.append(chat["latest_rant"])
    for r in rants:
        eid = f"rant:{r['username']}:{r['created_on']}"
        process_event(eid, "donation", r['username'], amount=r.get("amount_dollars"))

# ========== POLLER ==========
def poll_rumble():
    while True:
        try:
            r = requests.get(RUMBLE_API_URL, timeout=10)
            r.raise_for_status()
            data = r.json()

            parse_followers(data)
            parse_subscribers(data)
            parse_gifted_subs(data)

            for stream in data.get("livestreams", []):
                if stream.get("is_live"):
                    parse_chat_and_rants(stream.get("chat"))

        except Exception as e:
            print(f"[ERROR] Polling failed: {e}")

        time.sleep(POLL_INTERVAL)

# ========== START ==========
if __name__ == "__main__":
    # Start Rumble polling in a separate thread
    threading.Thread(target=poll_rumble, daemon=True).start()

    # Run Flask overlay server
    app.run(host="0.0.0.0", port=5000, debug=False)
