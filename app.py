from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from collections import deque
import time
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

alert_queue = deque()
displaying = False


@app.route("/")
def index():
    return render_template("index.html")


def alert_worker():
    global displaying

    while True:
        if alert_queue:
            displaying = True
            alert = alert_queue.popleft()

            socketio.emit("show_alert", alert)

            time.sleep(3)
        else:
            displaying = False
            time.sleep(0.5)


@socketio.on("alert")
def handle_alert(data):
    alert_type = data.get("Type", "Alert")
    username = data.get("USERNAME", "Someone")
    amount = data.get("Amount")

    if alert_type.lower() == "follow":
        message = f"{username} just followed!"
    elif alert_type.lower() == "donation" and amount:
        message = f"{username} donated ${amount}!"
    else:
        message = f"{username} triggered {alert_type}"

    alert_queue.append({
        "message": message,
        "type": alert_type
    })


threading.Thread(target=alert_worker, daemon=True).start()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
