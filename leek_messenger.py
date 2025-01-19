#!/usr/bin/env python3
import os
import sys

# --- Auto Virtual Environment Setup ---
# If we're not running inside a virtual environment, create one,
# install dependencies, and then re-launch this script.
if sys.prefix == sys.base_prefix:
    import subprocess
    import venv

    # Define path to the virtual environment directory (relative to this file)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(current_dir, 'venv')

    # Create the venv if it doesn't exist
    if not os.path.exists(venv_dir):
        print("Creating virtual environment...")
        venv.create(venv_dir, with_pip=True)

    # Determine paths to the virtual environment's executables
    if os.name == 'nt':
        python_executable = os.path.join(venv_dir, 'Scripts', 'python.exe')
        pip_executable = os.path.join(venv_dir, 'Scripts', 'pip.exe')
    else:
        python_executable = os.path.join(venv_dir, 'bin', 'python')
        pip_executable = os.path.join(venv_dir, 'bin', 'pip')

    # Upgrade pip and install required packages
    print("Installing required packages (PySocks, requests)...")
    subprocess.check_call([pip_executable, 'install', '--upgrade', 'pip'])
    subprocess.check_call([pip_executable, 'install', 'PySocks', 'requests'])

    # Relaunch the script using the virtual environment's Python interpreter
    print("Restarting script inside the virtual environment...")
    os.execv(python_executable, [python_executable] + sys.argv)

# Now we are running inside the virtual environment.
# --- End of Auto Virtual Environment Setup ---

import threading
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys
import json
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    filename=os.path.expanduser('~/tor_messaging.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Function to read the local onion address
def read_local_onion_address():
    try:
        with open(os.path.expanduser('~/hidden_service_hostname'), 'r') as file:
            onion_address = file.read().strip()
            return onion_address
    except Exception as e:
        print(f"Error reading local onion address: {e}")
        logging.error(f"Error reading local onion address: {e}")
        sys.exit(1)

# HTTP request handler for the server
class SimpleRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Read the message from the request
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            # Parse JSON data
            message = json.loads(post_data.decode('utf-8'))
            
            # Validate message structure
            required_fields = {"sender", "timestamp", "type", "content"}
            if not required_fields.issubset(message.keys()):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Invalid message format.')
                logging.warning("Received message with invalid format.")
                return
            
            # Process the message based on its type
            if message['type'] == 'text':
                log_content = f"Message from {message['sender']}: {message['content']}"
                print(f"\n[{message['timestamp']}] {log_content}")
                logging.info(log_content)
            elif message['type'] == 'command':
                log_content = f"Command from {message['sender']}: {message['content']}"
                print(f"\n[{message['timestamp']}] {log_content}")
                logging.info(log_content)
                # Implement command handling here if needed
            else:
                log_content = f"Unknown message type from {message['sender']}: {message['content']}"
                print(f"\n[{message['timestamp']}] {log_content}")
                logging.warning(log_content)
            
            # Send a response back to the client
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Invalid JSON format.')
            logging.error("Received message with invalid JSON format.")
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'Internal server error.')
            logging.error(f"Error processing incoming message: {e}")

    def log_message(self, format, *args):
        # Override to prevent printing to stdout/stderr
        return

# Function to start the server
def start_server(port):
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, SimpleRequestHandler)
    print(f"Server started on port {port}, waiting for incoming messages...")
    logging.info(f"Server started on port {port}.")
    httpd.serve_forever()

# Function to send messages to the remote onion address every second
def send_messages(remote_onion_address, local_onion_address):
    proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
    }
    url = f'http://{remote_onion_address}/'
    counter = 1
    while True:
        try:
            # Create a structured message
            message = {
                "sender": local_onion_address,
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "type": "text",  # or "command"
                "content": f"Hello! This is message {counter} from {local_onion_address}."
            }
            # Convert message to JSON
            json_message = json.dumps(message)
            
            # Send POST request
            response = requests.post(
                url,
                data=json_message,
                proxies=proxies,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code == 200:
                log_content = f"Sent message {counter} to {remote_onion_address}: {message['content']}"
                print(log_content)
                logging.info(log_content)
            else:
                log_content = f"Failed to send message {counter} to {remote_onion_address}: {response.text}"
                print(log_content)
                logging.warning(log_content)
            counter += 1
        except Exception as e:
            log_content = f"Error sending message to {remote_onion_address}: {e}"
            print(log_content)
            logging.error(log_content)
        time.sleep(1)

# Function to send custom messages based on user input
def send_custom_messages(remote_onion_address, local_onion_address):
    proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
    }
    url = f'http://{remote_onion_address}/'
    counter = 1
    print("Enter your messages below. Type 'exit' to quit.")
    while True:
        try:
            user_input = input("Your message: ")
            if user_input.lower() == 'exit':
                print("Exiting message sender.")
                break
            # Create a structured message
            message = {
                "sender": local_onion_address,
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "type": "text",  # or "command"
                "content": user_input
            }
            # Convert message to JSON
            json_message = json.dumps(message)
            
            # Send POST request
            response = requests.post(
                url,
                data=json_message,
                proxies=proxies,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code == 200:
                log_content = f"Sent message {counter} to {remote_onion_address}: {message['content']}"
                print(log_content)
                logging.info(log_content)
            else:
                log_content = f"Failed to send message {counter} to {remote_onion_address}: {response.text}"
                print(log_content)
                logging.warning(log_content)
            counter += 1
        except Exception as e:
            log_content = f"Error sending message to {remote_onion_address}: {e}"
            print(log_content)
            logging.error(log_content)

# Main function
def main():
    # Read the local onion address
    local_onion_address = read_local_onion_address()
    print(f"Your local onion address is: {local_onion_address}")
    logging.info(f"Local onion address: {local_onion_address}")
    
    # Ask for the remote onion address
    remote_onion_address = input("Enter the remote onion address (without 'http://'): ").strip()
    
    # Ensure the remote onion address is valid
    if not remote_onion_address.endswith('.onion'):
        print("Invalid onion address. Please ensure it ends with '.onion'.")
        logging.error("Invalid remote onion address entered.")
        sys.exit(1)
    
    # Start the server in a separate thread
    server_port = 8080  # Must match the port in your Tor hidden service configuration
    server_thread = threading.Thread(target=start_server, args=(server_port,))
    server_thread.daemon = True
    server_thread.start()
    
    # Choose between automatic and manual message sending
    choice = input("Choose message sending mode:\n1. Automatic (send every second)\n2. Manual (send custom messages)\nEnter 1 or 2: ").strip()
    
    if choice == '1':
        # Start sending messages to the remote onion address automatically
        send_messages(remote_onion_address, local_onion_address)
    elif choice == '2':
        # Start sending custom messages based on user input
        send_custom_messages(remote_onion_address, local_onion_address)
    else:
        print("Invalid choice. Exiting.")
        logging.error("Invalid messaging mode selected.")
        sys.exit(1)

if __name__ == "__main__":
    main()
