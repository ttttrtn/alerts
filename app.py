from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from collections import deque
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

alerts = deque()

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/alert")
def send_alert():
    alert_type = request.args.get("type", "alert")
    user = request.args.get("user", "Someone")
    amount = request.args.get("amount")

    if alert_type.lower() == "follow":
        msg = f"{user} just followed!"
    elif alert_type.lower() == "donation" and amount:
        msg = f"{user} donated ${amount}!"
    else:
        msg = f"{user} triggered {alert_type}"

    alerts.append({
        "message": msg,
        "type": alert_type
    })

    return jsonify({"status": "sent", "message": msg})


def alert_worker():
    while True:
        if alerts:
            alert = alerts.popleft()
            socketio.emit("show_alert", alert)
            time.sleep(3)
        else:
            time.sleep(1)


threading.Thread(target=alert_worker, daemon=True).start()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
