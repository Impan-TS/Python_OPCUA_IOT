from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
from opcua import Client
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app)

# Replace with your OPC UA server URL
OPC_UA_URL = "opc.tcp://DESKTOP-BSC7DMC:53530/OPCUA/SimulationServer"

# Create an OPC UA client instance
client = Client(OPC_UA_URL)

# Global variable to hold the latest values
latest_values = {}

def read_values_periodically():
    global latest_values
    while True:
        try:
            client.connect()  # Connect to the OPC UA server
            
            # Define your Node IDs here
            node_ids = {
                "Counter": "ns=3;i=1008",
                "Random": "ns=3;i=1003",
                "Sawtooth": "ns=3;i=1004",
                "Sinusoid": "ns=3;i=1005",
                "Square": "ns=3;i=1006",
                "Triangle": "ns=3;i=1007"
            }
            
            for name, node_id in node_ids.items():
                node = client.get_node(node_id)
                latest_values[name] = node.get_value()  # Read the value
            
            # Emit the latest values to all connected clients
            socketio.emit('update', latest_values)
            
            client.disconnect()  # Disconnect from the server
            time.sleep(1)  # Wait for 1 second before the next read
        except Exception as e:
            print(f"Error reading values: {str(e)}")
            time.sleep(1)  # Wait before retrying in case of error

@app.route('/write', methods=['POST'])
def write_value():
    try:
        data = request.json
        node_id = data.get('node_id')
        value = float(data.get('value'))  # Ensure the value is treated as a float

        client.connect()  # Connect to the OPC UA server
        node = client.get_node(node_id)
        node.set_value(value)  # Write the value

        return jsonify({"status": "success", "node_id": node_id, "new_value": value})
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        client.disconnect()  # Disconnect from the server

@app.route('/')
def index():
    return render_template('index.html')  # Render the HTML template

if __name__ == '__main__':
    # Start the background thread to read values periodically
    thread = threading.Thread(target=read_values_periodically)
    thread.daemon = True  # Daemonize thread
    thread.start()

    socketio.run(app, host='127.0.0.1', port=7000, debug=True)