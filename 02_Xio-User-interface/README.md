# Clay Create — Operator Interface
### Web-based session management dashboard for the Clay Create fabrication system

This repository contains the **operator interface** component of Clay Create — a real-time web dashboard that manages sculpting sessions and communicates with Grasshopper to feed live session data into the geometry generation pipeline.


> **Note:** This interface is one component of the full system. Depth camera processing, AI geometry generation, and projector calibration are developed separately by other team members.

---

## System Overview

```
Operator Web Interface (Browser)
        ↓
Flask Server (app.py)
        ↓
gh_state.json (shared state file)
        ↓
Grasshopper (CC — Session State Reader)
        ↓
Grid Visualizer (Rhino viewport)
        ↓
Pattern Generation Script (to be connected)
```

---

## Requirements

- Python 3.10+
- Rhino 7 / Grasshopper
- A browser (Chrome recommended)
- All devices on the same WiFi network

Install Python dependencies:

```bash
pip install flask flask-socketio==5.3.6 python-socketio==5.10.0 python-engineio==4.8.0 eventlet
```

---

## Getting Started

### 1. Download and set up

Clone or download this repository and navigate to the project folder:

```bash
cd clay_create
```

### 2. Run the Flask server

```bash
python app.py
```

You should see:
```
[Clay Create] Server running on http://0.0.0.0:5000
[UDP] Listening on port 6005
```

### 3. Open the operator dashboard

On the same machine open your browser and go to:
```
http://127.0.0.1:5000
```

To access from another device (tablet, laptop) on the same WiFi network, find your local IP address:
```bash
ipconfig   # Windows
```
Then open:
```
http://YOUR_LOCAL_IP:5000
```
Example: `http://192.168.1.45:5000`

### 4. Start a session

1. Set the number of **columns**, **rows** and **participants**
2. Click **Start session**
3. Enter the name of the first participant — they will sculpt Block 1
4. As each block is completed, the system unlocks adjacent blocks for the next participant

---

## Grasshopper Setup

### CC — Session State Reader

This GHPython component reads the session state from `gh_state.json` and outputs:

| Output | Type | Description |
|---|---|---|
| `bi` | int | Active block index (0-based), -1 if none |
| `cols` | int | Grid columns |
| `rows` | int | Grid rows |
| `active` | bool | True if a block is currently being sculpted |
| `sculptor` | str | Name of the active participant |
| `dn` | str | Comma-separated indices of completed blocks |
| `status` | str | Debug status message |

**Important:** Update the `FILE_PATH` variable in the script to match your local path:
```python
FILE_PATH = r"C:\YOUR\PATH\clay_create\gh_state.json"
```

### CC — Grid Visualizer

Generates a real-time grid in the Rhino viewport showing:
- 🟢 **Green** — block currently being sculpted
- ⬛ **Dark** — completed blocks
- ⬜ **Light grey** — pending blocks

Connect the outputs of **CC — Session State Reader** to this component:
- `bi` → `block_index`
- `cols` → `cols`
- `rows` → `rows`

### Connecting to Pattern Generation

The `bi` output (active block index) is the main connection point for the pattern generation script. When `active = True`, the system is ready to receive geometry for projection.

---

## Project Structure

```
clay_create/
├── app.py              # Flask server — WebSockets, UDP, session management
├── state.py            # Session state logic — block unlock, participant reuse
├── requirements.txt    # Python dependencies
├── gh_state.json       # Auto-generated — shared state between Flask and GH
├── templates/
│   └── index.html      # Operator dashboard (dark mode UI)
└── static/             # Static assets
```

---

## Communication Flow

| Direction | Protocol | Port | Description |
|---|---|---|---|
| Browser → Flask | WebSocket | 5000 | UI events (assign, complete, reset) |
| Flask → Browser | WebSocket | 5000 | Real-time state updates |
| Grasshopper → Flask | UDP | 6005 | Geometry / projection data from GH |
| Flask → Grasshopper | File | — | `gh_state.json` updated on every event |

---

## Credits

Developed as part of the **MRAC01 Hardware III** workshop at **IAAC Barcelona**.  
This interface is one component of the Clay Create system — a co-creative fabrication research project exploring human-in-the-loop making between AI, human action, and material resistance.
