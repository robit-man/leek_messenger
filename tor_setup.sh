#!/bin/bash

# Define variables
TOR_SERVICE_NAME="tor@default"
HIDDEN_SERVICE_DIR="/var/lib/tor/hidden_service"
TORRC_PATH="/etc/tor/torrc"
BACKUP_DIR="/var/backups/tor"
LOG_FILE="/var/log/tor_setup.log"
LOCAL_SERVICE_PORT=8080
TOR_SOCKS_PORT=9050

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Install Tor if not installed
install_tor() {
    log_message "Checking if Tor is installed..."
    if ! command -v tor > /dev/null; then
        log_message "Tor is not installed. Installing..."
        sudo apt-get update
        sudo apt-get install -y tor
    else
        log_message "Tor is already installed."
    fi
}

# Set up the hidden service
setup_hidden_service() {
    log_message "Setting up hidden service directory..."
    sudo mkdir -p "$HIDDEN_SERVICE_DIR"
    sudo chown -R debian-tor:debian-tor "$HIDDEN_SERVICE_DIR"
    sudo chmod 700 "$HIDDEN_SERVICE_DIR"
    log_message "Hidden service directory is set with proper ownership and permissions."
}

# Backup existing Tor configuration
backup_torrc() {
    log_message "Backing up existing Tor configuration..."
    sudo mkdir -p "$BACKUP_DIR"
    if [ -f "$TORRC_PATH" ]; then
        sudo cp "$TORRC_PATH" "$BACKUP_DIR/torrc_backup_$(date +%Y%m%d%H%M%S)"
        log_message "Tor configuration backed up to $BACKUP_DIR."
    else
        log_message "No existing Tor configuration found to back up."
    fi
}

# Update Tor configuration to include hidden service settings
configure_torrc() {
    log_message "Updating Tor configuration at $TORRC_PATH..."

    # Ensure the necessary directives are present
    sudo sed -i '/^User /d' "$TORRC_PATH"
    sudo sed -i '/^DataDirectory /d' "$TORRC_PATH"
    sudo sed -i '/^HiddenServiceDir /d' "$TORRC_PATH"
    sudo sed -i '/^HiddenServicePort /d' "$TORRC_PATH"

    sudo bash -c "cat >> $TORRC_PATH <<EOL
# Tor configuration generated by setup script
User debian-tor
DataDirectory /var/lib/tor

# Hidden Service Configuration
HiddenServiceDir $HIDDEN_SERVICE_DIR
HiddenServicePort 80 127.0.0.1:$LOCAL_SERVICE_PORT
EOL"

    log_message "Tor configuration updated."

    # Verify the Tor configuration
    log_message "Verifying Tor configuration syntax..."
    if ! sudo tor --verify-config -f "$TORRC_PATH"; then
        log_message "[ERROR] Tor configuration is invalid."
        exit 1
    else
        log_message "Tor configuration is valid."
    fi
}

# Restart Tor service
restart_tor() {
    log_message "Restarting Tor service..."
    sudo systemctl restart "$TOR_SERVICE_NAME"
    sleep 5  # Give Tor some time to start
    if ! systemctl is-active --quiet "$TOR_SERVICE_NAME"; then
        log_message "[ERROR] Tor service failed to start."
        log_message "Checking Tor logs for errors..."
        sudo journalctl -u "$TOR_SERVICE_NAME" -b --no-pager | tail -n 50 | tee -a "$LOG_FILE"
        exit 1
    else
        log_message "Tor service restarted successfully."
    fi
}

# Ensure Tor starts at boot
enable_tor_on_boot() {
    log_message "Enabling Tor to start on boot..."
    sudo systemctl enable "$TOR_SERVICE_NAME"
    if systemctl is-enabled --quiet "$TOR_SERVICE_NAME"; then
        log_message "Tor service enabled to start on boot."
    else
        log_message "[ERROR] Failed to enable Tor to start on boot."
    fi
}

# Display the hidden service .onion address and copy it to a user-accessible location
display_and_copy_hidden_service_address() {
    log_message "Attempting to read hidden service hostname..."
    if [ -f "$HIDDEN_SERVICE_DIR/hostname" ]; then
        local onion_address
        onion_address=$(sudo cat "$HIDDEN_SERVICE_DIR/hostname")
        if [ -n "$onion_address" ]; then
            echo "[INFO] Hidden service address: $onion_address"
            log_message "Hidden service address: $onion_address"

            # Copy the hostname to a user-accessible location
            USER_ONION_FILE="$HOME/hidden_service_hostname"
            echo "$onion_address" > "$USER_ONION_FILE"
            chmod 644 "$USER_ONION_FILE"
            log_message "Copied hidden service address to $USER_ONION_FILE"
        else
            log_message "[ERROR] Hidden service hostname is empty."
        fi
    else
        log_message "[ERROR] Hidden service hostname file is missing."
    fi
}

# Verify that the local service is running on the specified port
verify_local_service() {
    log_message "Verifying that the local service on port $LOCAL_SERVICE_PORT is running..."
    if nc -zv 127.0.0.1 "$LOCAL_SERVICE_PORT" 2>&1 | grep -q succeeded; then
        log_message "Local service on port $LOCAL_SERVICE_PORT is running."
    else
        log_message "[WARNING] Local service on port $LOCAL_SERVICE_PORT is not running."
        log_message "Please ensure your service is running for the hidden service to function properly."
    fi
}

# Main function
main() {
    log_message "Starting Tor setup script..."

    install_tor
    setup_hidden_service
    backup_torrc
    configure_torrc
    verify_local_service
    restart_tor
    enable_tor_on_boot

    # Wait for the hidden service to initialize
    log_message "Waiting for the hidden service to initialize..."
    sleep 30

    display_and_copy_hidden_service_address

    log_message "Tor setup script completed."
}

main