"""
GHPython component — Clay Create UDP Sender
Paste this code into a GHPython component in Grasshopper.

Inputs:
  send       (bool)        — Button or toggle to trigger send
  block_idx  (int)         — Index of the block whose heightmap to send
  heightmap  (DataTree)    — 2D grid of height values (0.0 to 1.0), one branch per row
  flask_ip   (str)         — IP of the Flask server (default: 127.0.0.1)
  flask_port (int)         — UDP port (default: 6005)

Outputs:
  out        (str)         — Status message
"""

import socket
import json
import rhinoscriptsyntax as rs

# ── DEFAULTS ───────────────────────────────────────────────────────────────────
_ip   = flask_ip   if flask_ip   else "127.0.0.1"
_port = flask_port if flask_port else 6005

def send_udp(payload_dict, ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = json.dumps(payload_dict).encode('utf-8')
    sock.sendto(data, (ip, port))
    sock.close()

def tree_to_2d(tree):
    """Convert a Grasshopper DataTree to a Python 2D list."""
    result = []
    for i in range(tree.BranchCount):
        branch = list(tree.Branch(i))
        result.append([float(v) for v in branch])
    return result

if send:
    try:
        hm_2d = tree_to_2d(heightmap)
        payload = {
            "type":        "heightmap",
            "block_index": int(block_idx),
            "data":        hm_2d
        }
        send_udp(payload, _ip, _port)
        out = f"Sent heightmap for block {block_idx} to {_ip}:{_port}  ({len(hm_2d)}x{len(hm_2d[0])} grid)"
    except Exception as e:
        out = f"Error: {e}"
else:
    out = "Ready — toggle 'send' to transmit heightmap."
