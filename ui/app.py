import json
import os
import socket
import threading
import time as _time
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from state import SessionState

app = Flask(__name__)
app.config['SECRET_KEY'] = 'clay_create_secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)

session = SessionState()

# ─── UDP RECEIVER (from Grasshopper) ──────────────────────────────────────────
UDP_IP   = "0.0.0.0"
UDP_PORT = 6005

def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"[UDP] Listening on port {UDP_PORT}")
    while True:
        try:
            data, _ = sock.recvfrom(65535)
            payload = json.loads(data.decode('utf-8'))
            handle_gh_message(payload)
        except Exception as e:
            print(f"[UDP] Error: {e}")

def handle_gh_message(payload):
    elements = payload.get("elements", [])
    curves   = payload.get("curves",   [])
    meta     = payload.get("meta",     {})
    session.set_projection(elements, curves, meta)
    socketio.emit('projection_update', {
        'elements': elements,
        'curves':   curves,
        'meta':     meta
    })
    block_idx = meta.get("block_index", "?")
    print(f"[UDP] GH update — {len(elements)} elements, {len(curves)} curves, block={block_idx}")

# ─── HTTP ROUTES ───────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/projection')
def projection():
    return render_template('projection.html')

@app.route('/api/state')
def get_state():
    return jsonify(session.to_dict())

@app.route('/api/session/start', methods=['POST'])
def start_session():
    data = request.get_json()
    cols = data.get('cols', 3)
    rows = data.get('rows', 3)
    participants = data.get('participants', 4)
    session.start(cols, rows, participants)
    session.session_time = 0
    socketio.emit('session_started', session.to_dict())
    print(f"[Session] Started — {cols}x{rows} grid, {participants} participants")
    return jsonify({'status': 'ok', 'state': session.to_dict()})

@app.route('/api/block/assign', methods=['POST'])
def assign_block():
    data = request.get_json()
    block_idx = data.get('block_index')
    name = data.get('name', 'Participant')
    result = session.assign_block(block_idx, name)
    if result['success']:
        socketio.emit('block_assigned', session.to_dict())
        send_to_grasshopper({'type': 'block_active', 'block_index': block_idx, 'sculptor': name})
        print(f"[Session] Block {block_idx} assigned to {name}")
    return jsonify(result)

@app.route('/api/block/complete', methods=['POST'])
def complete_block():
    data = request.get_json()
    block_idx = data.get('block_index')
    result = session.complete_block(block_idx)
    if result['success']:
        socketio.emit('block_completed', session.to_dict())
        send_to_grasshopper({'type': 'block_done', 'block_index': block_idx})
        print(f"[Session] Block {block_idx} completed")
    return jsonify(result)

@app.route('/api/block/reset', methods=['POST'])
def reset_block():
    data = request.get_json()
    block_idx = data.get('block_index')
    result = session.reset_block(block_idx)
    if result['success']:
        socketio.emit('block_reset', session.to_dict())
        send_to_grasshopper({'type': 'block_reset', 'block_index': block_idx})
        print(f"[Session] Block {block_idx} reset")
    return jsonify(result)

@app.route('/api/session/reset', methods=['POST'])
def reset_session():
    session.reset()
    session.session_time = 0
    socketio.emit('session_reset', {})
    print("[Session] Full reset")
    return jsonify({'status': 'ok'})

# ─── UDP SENDER (to Grasshopper) — non-blocking ───────────────────────────────
GH_IP      = "127.0.0.1"
GH_PORT    = 6006
STATE_FILE = os.path.join(os.path.dirname(__file__), 'gh_state.json')

def _gh_send_worker(payload):
    """Runs in background thread — never blocks the main request."""
    try:
        payload['state'] = session.to_dict()
        with open(STATE_FILE, 'w') as f:
            json.dump(payload, f)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.1)   # 100 ms max, non-blocking
        sock.sendto(json.dumps(payload).encode('utf-8'), (GH_IP, GH_PORT))
        sock.close()
        print(f"[UDP→GH] {payload.get('type')} — block={payload.get('block_index')}")
    except Exception as e:
        print(f"[UDP] Send error: {e}")

def send_to_grasshopper(payload):
    """Fire-and-forget: never delays the HTTP response."""
    threading.Thread(target=_gh_send_worker, args=(payload,), daemon=True).start()

# ─── WEBSOCKET EVENTS ──────────────────────────────────────────────────────────
@socketio.on('connect')
def on_connect():
    emit('state_sync', session.to_dict())
    proj = session.get_projection()
    if proj:
        emit('projection_update', proj)
    print("[WS] Client connected")

@socketio.on('disconnect')
def on_disconnect():
    print("[WS] Client disconnected")

# ─── SESSION TIMER ─────────────────────────────────────────────────────────────
def session_timer():
    while True:
        _time.sleep(1)
        if not session.started:
            continue
        session.session_time = getattr(session, 'session_time', 0) + 1
        ab = session.active_block
        block_elapsed = 0
        if ab is not None and 0 <= ab < len(session.blocks):
            b = session.blocks[ab]
            if b.get('start_time'):
                block_elapsed = int(_time.time() - b['start_time'])
        socketio.emit('tick', {
            'session_time':  session.session_time,
            'block_elapsed': block_elapsed,
        })

# ─── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    session.session_time = 0
    threading.Thread(target=udp_listener,  daemon=True).start()
    threading.Thread(target=session_timer, daemon=True).start()
    print("[Clay Create] Server     →  http://0.0.0.0:5000")
    print("[Clay Create] Projection →  http://0.0.0.0:5000/projection")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
