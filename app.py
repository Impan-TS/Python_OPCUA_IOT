from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
from opcua import Client
import threading
import time
import plotly
import json
import pyodbc
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash, make_response
from datetime import datetime, timedelta
from werkzeug.utils import redirect
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, ValidationError
import bcrypt

app = Flask(__name__)
app.secret_key = 'xyzsdfg'
socketio = SocketIO(app)

# Database configuration
DB_SERVER = 'DESKTOP-BSC7DMC\SQLEXPRESS'
DB_DATABASE = 'tse_data'
DB_USER = 'sa'
DB_PASSWORD = 'tiger'

# Connection string
connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={DB_SERVER};DATABASE={DB_DATABASE};UID={DB_USER};PWD={DB_PASSWORD}'


# # Function to create a connection
# def create_connection():
#     return pyodbc.connect(connection_string)

# Function to create a connection
def create_connection():
    while True:
        try:
            conn = pyodbc.connect(connection_string)
            return conn
        except pyodbc.Error as e:
            print(f"Error connecting to database: {e}")
            # Handle specific error cases if needed, or retry
            # Example: Handle specific error codes or types of errors
            # Check documentation for pyodbc for specific error handling

        except Exception as e:
            print(f"Unexpected error during connection: {e}")
            return None  # Handle other exceptions as needed

# Connect to the database
def connect_to_db():
    # conn_str = 'ODBC Driver 17 for SQL Server={SQL Server};SERVER=' + DESKTOP-BSC7DMCSQLEXPRESS + ';DATABASE=' + tse_data + ';UID=' + sa + ';PWD=' + tiger
    # conn_str = 'DRIVER={SQL Server};SERVER=' + DB_SERVER + ';DATABASE=' + DB_DATABASE + ';UID=' + DB_USER + ';PWD=' + DB_PASSWORD
    conn_str = 'DRIVER={SQL Server};SERVER=' + DB_SERVER + ';DATABASE=' + DB_DATABASE + ';UID=' + DB_USER + ';PWD=' + DB_PASSWORD
    return pyodbc.connect(conn_str)

# OPC UA server URL
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
            
            # Define Node IDs here
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
            
            socketio.emit('gauge_update', {
                "Random": latest_values.get("Random", 0),
                "Counter": latest_values.get("Counter", 0),
                "Sawtooth": latest_values.get("Sawtooth", 0)
            })
            
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
        
@app.route('/', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        # Process the login form submission here
        username = request.form['username']
        password = request.form['password']
        
        # Check the username and password (you can move this to a separate function)
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()

        if user:
            session['userloggedin'] = True
            session['userid'] = user.id  # Assuming 'id' is the column name for the user ID
            session['username'] = user.username  # Assuming 'username' is the column name for the username
            conn.close()  # Close the connection after use
            return redirect(url_for('tsepage'))  # Redirect to the tse page
        else:
            # Invalid login
            flash('Invalid username or password')
            conn.close()  # Close the connection after use
            return render_template('User management/userlogin.html')  # Show login page again

    # Handle GET requests as usual
    response = make_response(render_template('User management/userlogin.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/tse', methods=['GET', 'POST'])
def tsepage():
    # Check if the user is logged in
    if 'userloggedin' not in session:
        # If not logged in, redirect to the user login page
        return redirect(url_for('user_login'))
    
    else:
        response = make_response(render_template('iot/tse.html'))
        # Add cache-control header to prevent caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response
    
@app.route('/userlogin', methods=['GET', 'POST'])
def userlogin():
    # Check if the user is already logged in
    if 'userloggedin' in session:
        # If already logged in, redirect to the report page
        return redirect(url_for('tsepage'))

    message = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Establish a database connection
        conn = create_connection()
        cursor = conn.cursor()
        
        # Use a case-sensitive collation for comparison
        cursor.execute("SELECT * FROM users WHERE username = ? COLLATE Latin1_General_CS_AS AND password = ?", (username, password,))
        user = cursor.fetchone()
        
        if user:
            session['userloggedin'] = True
            session['userid'] = user.id  # Assuming 'id' is the column name for the user ID
            session['username'] = user.username  # Assuming 'username' is the column name for the username
            message = 'Logged in successfully!'
            conn.close()  # Close the connection after use
            return redirect(url_for('tsepage'))  # This should redirect to the /tse route

        else:
            # Close the connection in case of failure
            conn.close()
            # Display error message only when login attempt fails
            message = 'Invalid username or password'
    
    # Render the login page
    response = make_response(render_template('User management/userlogin.html', message=message))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/logout')
def logout():
    # Clear user session data
    session.pop('userloggedin', None)
    session.pop('userid', None)
    session.pop('username', None)

    response = make_response(redirect(url_for('user_login')))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# @app.route('/logout')
# def logout():
#     session.pop('username', None)  # Clear the session
#     return redirect(url_for('user_login'))  # Redirect to login page

# @app.route('/tse')
# def tse():
#     msg = {'payload': 0}
#     return render_template('iot/tse.html', msg=msg)  # Render the tse.html template

@app.route('/index')
def index():
    msg = {'payload': 0}
    return render_template('iot/index.html', msg=msg)  # Render the HTML template

@app.route('/dashboard')
def dashboard():
    msg = {'payload': 0}
    return render_template('iot/dashboard.html', msg=msg)  # Render the HTML template

@app.route('/spinning2')
def spinning2():
    msg = {'payload': latest_values}  # Pass the latest values to the template
    return render_template('iot/spinning2.html', msg=msg, active_submodule='departmentsSubmodules')

if __name__ == '__main__':
    # Start the background thread to read values periodically
    thread = threading.Thread(target=read_values_periodically)
    thread.daemon = True  # Daemonize thread
    thread.start()
    app.run(host="127.0.0.1", port=7000)
    socketio.run(app, host='127.0.0.1', port=7000, debug=True)