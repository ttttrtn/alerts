from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

# Receive WebSocket messages
@socketio.on('alert')
def handle_alert(data):
    # Example data: {"Type":"Follow","Amount":null,"USERNAME":"Malik"}
    alert_type = data.get("Type", "Alert")
    username = data.get("USERNAME", "Someone")
    amount = data.get("Amount", None)

    # Build the message
    if alert_type.lower() == "follow":
        message = f"{username} just followed!"
    elif alert_type.lower() == "donation" and amount:
        message = f"{username} just donated ${amount}!"
    else:
        message = f"{username} triggered {alert_type}"

    # Send to all clients
    emit('show_alert', {"message": message, "type": alert_type}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
