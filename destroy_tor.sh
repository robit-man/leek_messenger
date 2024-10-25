#!/bin/bash

echo "Starting complete Tor cleanup..."

# Step 1: Kill all running Tor processes
echo "Terminating all active Tor processes..."
if pgrep -x "tor" > /dev/null; then
    sudo pkill -9 -x "tor" && echo "All Tor processes have been killed."
else
    echo "No active Tor processes found."
fi

# Step 2: Remove Tor service from system startup
echo "Disabling Tor service at startup..."
sudo systemctl disable tor --now &>/dev/null

# Step 3: Remove Tor package and configuration files
echo "Removing Tor and associated packages..."
sudo apt purge -y tor tor-geoipdb
sudo apt autoremove -y  # Remove unnecessary dependencies

# Step 4: Clear any residual Tor directories
echo "Cleaning up residual Tor files and directories..."
sudo rm -rf /var/lib/tor
sudo rm -rf /var/log/tor
sudo rm -rf /etc/tor
sudo rm -rf $HOME/my_tor_data

echo "Tor has been completely removed from this system."
