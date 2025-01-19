#!/usr/bin/env python3
import os
import sys

# === Auto Virtual Environment Setup ===
# If not running inside a virtual environment, create one, install dependencies,
# and re-launch this script using the venv.
if sys.prefix == sys.base_prefix:
    import subprocess
    import venv

    current_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(current_dir, 'venv')

    if not os.path.exists(venv_dir):
        print("Creating virtual environment...")
        venv.create(venv_dir, with_pip=True)

    if os.name == 'nt':
        python_executable = os.path.join(venv_dir, 'Scripts', 'python.exe')
        pip_executable = os.path.join(venv_dir, 'Scripts', 'pip.exe')
    else:
        python_executable = os.path.join(venv_dir, 'bin', 'python')
        pip_executable = os.path.join(venv_dir, 'bin', 'pip')

    print("Installing required packages (PySocks, requests, cryptography, qrcode)...")
    subprocess.check_call([pip_executable, 'install', '--upgrade', 'pip'])
    subprocess.check_call([pip_executable, 'install', 'PySocks', 'requests', 'cryptography', 'qrcode', 'pillow'])

    print("Restarting script inside the virtual environment...")
    os.execv(python_executable, [python_executable] + sys.argv)

# === Now running inside the virtual environment ===

import threading
import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys
import json
from datetime import datetime
import logging
from cryptography.fernet import Fernet

# Global variable to control encryption mode and store the key (if any)
encryption_mode = False
encryption_key = None  # Will hold a Fernet key (bytes) if encryption is used

# Configure logging
logging.basicConfig(
    filename=os.path.expanduser('~/tor_messaging.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Utility: Load or create .env file for encryption key ---
def load_or_create_env():
    global encryption_key
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    key = None
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith("ENCRYPTION_KEY="):
                    key = line.strip().split("=", 1)[1]
                    break
    if key is None:
        # Generate new Fernet key
        key = Fernet.generate_key().decode('utf-8')
        with open(env_path, 'w') as f:
            f.write(f"ENCRYPTION_KEY={key}\n")
        print(f"[+] New encryption key generated and saved in .env: {key}")
    else:
        print(f"[+] Encryption key loaded from .env: {key}")
    encryption_key = key.encode('utf-8')

# --- Utility: Generate QR Code with local onion address and encryption key (if available) ---
def generate_qr_code(local_onion_address):
    import qrcode
    import io
    # Build the QR payload
    qr_data = {"local_onion": local_onion_address}
    if encryption_key is not None:
        qr_data["encryption_key"] = encryption_key.decode('utf-8')
    json_data = json.dumps(qr_data, indent=2)
    
    try:
        # Create the QR code image using qrcode.make
        img = qrcode.make(json_data)
        # Save the QR code to a buffer then write it to a file
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_onion_qr.png")
        with open(file_path, "wb") as f:
            f.write(buf.getvalue())
        print(f"[+] QR code generated and saved to: {file_path}")
        logging.info(f"QR code generated and saved to: {file_path}")
    except Exception as e:
        logging.error(f"Failed to generate QR code: {e}")
        print(f"Failed to generate QR code: {e}")

# Function to read the local onion address from a file
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
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        # If encryption mode is active, attempt to decrypt the payload
        if encryption_mode:
            try:
                f = Fernet(encryption_key)
                post_data = f.decrypt(post_data)
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Invalid encrypted message or decryption failed.')
                logging.error("Decryption failed: " + str(e))
                return

        try:
            message = json.loads(post_data.decode('utf-8'))
            required_fields = {"sender", "timestamp", "type", "content"}
            if not required_fields.issubset(message.keys()):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Invalid message format.')
                logging.warning("Received message with invalid format.")
                return
            
            if message['type'] == 'text':
                log_content = f"Message from {message['sender']}: {message['content']}"
                print(f"\n[{message['timestamp']}] {log_content}")
                logging.info(log_content)
            elif message['type'] == 'command':
                log_content = f"Command from {message['sender']}: {message['content']}"
                print(f"\n[{message['timestamp']}] {log_content}")
                logging.info(log_content)
            else:
                log_content = f"Unknown message type from {message['sender']}: {message['content']}"
                print(f"\n[{message['timestamp']}] {log_content}")
                logging.warning(log_content)
            
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
        return

# Function to start the server
def start_server(port):
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, SimpleRequestHandler)
    print(f"Server started on port {port}, waiting for incoming messages...")
    logging.info(f"Server started on port {port}.")
    httpd.serve_forever()

# Function to send messages automatically every second
def send_messages(remote_onion_address, local_onion_address):
    proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
    }
    url = f'http://{remote_onion_address}/'
    counter = 1
    while True:
        try:
            message = {
                "sender": local_onion_address,
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "type": "text",
                "content": f"Hello! This is message {counter} from {local_onion_address}."
            }
            json_message = json.dumps(message)
            # Encrypt payload if encryption mode is active.
            if encryption_mode:
                f = Fernet(encryption_key)
                json_message = f.encrypt(json_message.encode('utf-8'))
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
            message = {
                "sender": local_onion_address,
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "type": "text",
                "content": user_input
            }
            json_message = json.dumps(message)
            if encryption_mode:
                f = Fernet(encryption_key)
                json_message = f.encrypt(json_message.encode('utf-8'))
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
    global encryption_mode
    # Read the local onion address
    local_onion_address = read_local_onion_address()
    print(f"Your local onion address is: {local_onion_address}")
    logging.info(f"Local onion address: {local_onion_address}")
    
    # Ask for the remote onion address
    remote_onion_address = input("Enter the remote onion address (without 'http://'): ").strip()
    if not remote_onion_address.endswith('.onion'):
        print("Invalid onion address. Please ensure it ends with '.onion'.")
        logging.error("Invalid remote onion address entered.")
        sys.exit(1)
    
    # Present three messaging options.
    print("Choose message sending mode:")
    print("1. Automatic (send every second, plain text)")
    print("2. Manual (send custom messages, plain text)")
    print("3. Encrypted (messages will be encrypted/decrypted automatically)")
    choice = input("Enter 1, 2, or 3: ").strip()
    
    if choice == '1':
        encryption_mode = False
    elif choice == '2':
        encryption_mode = False
    elif choice == '3':
        encryption_mode = True
        load_or_create_env()
    else:
        print("Invalid choice. Exiting.")
        logging.error("Invalid messaging mode selected.")
        sys.exit(1)
    
    # Generate a QR code with a JSON object containing your local onion and,
    # if available, the encryption key.
    generate_qr_code(local_onion_address)
    
    # Start the HTTP server in a separate thread.
    server_port = 8080  # Adjust if needed (must match your Tor hidden service config)
    server_thread = threading.Thread(target=start_server, args=(server_port,))
    server_thread.daemon = True
    server_thread.start()
    
    if choice == '1':
        send_messages(remote_onion_address, local_onion_address)
    elif choice == '2':
        send_custom_messages(remote_onion_address, local_onion_address)
    elif choice == '3':
        # Ask which encrypted mode to use (automatic or manual)
        print("Choose encrypted message sending mode:")
        print("1. Automatic (send every second)")
        print("2. Manual (send custom messages)")
        enc_choice = input("Enter 1 or 2: ").strip()
        if enc_choice == '1':
            send_messages(remote_onion_address, local_onion_address)
        elif enc_choice == '2':
            send_custom_messages(remote_onion_address, local_onion_address)
        else:
            print("Invalid choice. Exiting.")
            logging.error("Invalid encrypted messaging mode selected.")
            sys.exit(1)

if __name__ == "__main__":
    main()
