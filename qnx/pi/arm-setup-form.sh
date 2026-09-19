#!/bin/sh
# Arm the thermal-monitor setup form for a demo.
#
# Gives the wired port (cgem0) its fixed demo address and starts the form
# server if it is not already listening. Safe to run repeatedly. Invoked from
# ~/.profile so an interactive SSH login arms everything automatically.

sudo ifconfig cgem0 10.44.0.1 netmask 255.255.255.0

if python3 -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(('127.0.0.1',8080))==0 else 1)"; then
  echo "setup form already running on :8080"
else
  nohup python3 "$HOME/setup_server.py" >"$HOME/setup_server.log" 2>&1 &
  echo "setup form started on :8080 (log: $HOME/setup_server.log)"
fi
