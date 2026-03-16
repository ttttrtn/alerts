from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from collections import deque
import eventlet

eventlet.monkey_patch()  # Needed for proper async with SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

alert_queue = deque()
is_displaying = False

@app.route('/')
def index():
    return render_template('index.html')

def send_next_alert():
    global is_displaying
    if alert_queue:
        alert = alert_queue.popleft()
        socketio.emit('show_alert', alert, broadcast=True)
        is_displaying = True
        # Wait 3 seconds then show the next alert
        socketio.start_background_task(wait_and_show_next)

    else:
        is_displaying = False

def wait_and_show_next():
    eventlet.sleep(3)
    send_next_alert()

@socketio.on('alert')
def handle_alert(data):
    """
    Example data: {"Type":"Follow","Amount":null,"USERNAME":"Malik"}
    """
    alert_type = data.get("Type", "Alert")
    username = data.get("USERNAME", "Someone")
    amount = data.get("Amount", None)

    if alert_type.lower() == "follow":
        message = f"{username} just followed!"
    elif alert_type.lower() == "donation" and amount:
        message = f"{username} just donated ${amount}!"
    else:
        message = f"{username} triggered {alert_type}"

    alert_queue.append({"message": message, "type": alert_type})

    # If nothing is displaying, start
    if not is_displaying:
        send_next_alert()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
