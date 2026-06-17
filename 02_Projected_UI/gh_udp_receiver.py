"""
GHPython component — Clay Create UDP Receiver
Paste this code into a GHPython component in Grasshopper.
Use a Timer component to poll every ~200ms.

Inputs:
  listen_port  (int)   — UDP port to listen on (default: 6006)
  enabled      (bool)  — Toggle to enable/disable listening

Outputs:
  msg_type     (str)   — Type of last received message
  block_index  (int)   — Block index from message
  sculptor     (str)   — Sculptor name (if available)
  raw          (str)   — Full raw JSON string
"""

import socket
import json

_port = listen_port if listen_port else 6006

msg_type    = ""
block_index = -1
sculptor    = ""
raw         = ""

if enabled:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", _port))
        sock.settimeout(0.05)   # non-blocking: 50ms timeout
        data, _ = sock.recvfrom(65535)
        sock.close()
        payload     = json.loads(data.decode('utf-8'))
        raw         = data.decode('utf-8')
        msg_type    = payload.get("type", "")
        block_index = int(payload.get("block_index", -1))
        sculptor    = payload.get("sculptor", "")
    except socket.timeout:
        raw = "No message received"
    except OSError as e:
        raw = f"Socket error: {e}"
    except Exception as e:
        raw = f"Error: {e}"
else:
    raw = "Receiver disabled."
