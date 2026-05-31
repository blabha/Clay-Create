import json
import os
import socket
import threading
import time as _time
import urllib.request
from flask import Flask, render_template, jsonify, request, Response
from flask_socketio import SocketIO, emit
from state import SessionState

app = Flask(__name__, template_folder='ui/templates', static_folder='ui/static')
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
    return render_template('projection.html')

@app.route('/projection')
def projection():
    resp = render_template('projection.html')
    from flask import make_response
    r = make_response(resp)
    r.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    r.headers['Pragma'] = 'no-cache'
    return r

@app.route('/api/ai-state')
def ai_state():
    try:
        with urllib.request.urlopen('http://localhost:8001/api/state', timeout=2) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return jsonify({
            'initialized': data.get('initialized', False),
            'cols':         data.get('cols', 0),
            'rows':         data.get('rows', 0),
            'current_tile': data.get('current_tile'),
            'completed':    data.get('completed', []),
        })
    except Exception:
        return jsonify({'initialized': False, 'cols': 0, 'rows': 0})


@app.route('/api/ai-heightmap')
def ai_heightmap():
    try:
        with urllib.request.urlopen('http://localhost:8001/api/master.png', timeout=2) as resp:
            data = resp.read()
        return Response(data, mimetype='image/png', headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate'
        })
    except Exception:
        return Response(status=404)


@app.route('/api/target-heatmap')
def target_heatmap():
    path = r'C:\Users\Bhavana\Documents\Hardware 3\z_Target heat_PNG_Outpumap_Colourt\target_heatmap.png'
    if not os.path.exists(path):
        return Response(status=404)
    with open(path, 'rb') as f:
        data = f.read()
    return Response(data, mimetype='image/png', headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate'
    })


@app.route('/api/progress-heatmap')
def progress_heatmap():
    path = r'C:\Users\Bhavana\Documents\Hardware 3\z_Target heatmap_Colour_PNG_Output\progress_heatmap.png'
    if not os.path.exists(path):
        return Response(status=404)
    with open(path, 'rb') as f:
        data = f.read()
    return Response(data, mimetype='image/png', headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate'
    })


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
        threading.Thread(target=_save_target_design, args=(block_idx,), daemon=True).start()
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

# ─── TARGET DESIGN ARCHIVE ────────────────────────────────────────────────────
_WORKSPACE          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TARGET_CURRENT_DIR = os.path.join(_WORKSPACE, "z_Target heat_PNG_Outpumap_Colourt")
_TARGET_DONE_DIR    = os.path.join(_WORKSPACE, "z_Completed Target Design")
_TARGET_FILE        = os.path.join(_TARGET_CURRENT_DIR, "target_heatmap.png")

def _save_target_design(block_idx):
    """Fetch tile's intended design from AI backend and save as current_target.jpg."""
    import shutil
    from io import BytesIO
    from PIL import Image as _PILImage
    try:
        os.makedirs(_TARGET_CURRENT_DIR, exist_ok=True)
        os.makedirs(_TARGET_DONE_DIR,    exist_ok=True)
        if os.path.exists(_TARGET_FILE):
            ts = _time.strftime("%Y%m%d_%H%M%S")
            shutil.move(_TARGET_FILE, os.path.join(_TARGET_DONE_DIR, f"target_{ts}.jpg"))
            print(f"[Target] Archived previous -> target_{ts}.jpg")
        with urllib.request.urlopen(
                f'http://localhost:8001/api/export/png/{block_idx}', timeout=3) as resp:
            png_data = resp.read()
        img = _PILImage.open(BytesIO(png_data)).convert('RGB')
        img.save(_TARGET_FILE, 'JPEG', quality=95)
        print(f"[Target] Saved tile {block_idx} design -> {_TARGET_FILE}")
    except Exception as e:
        print(f"[Target] Could not save target design: {e}")


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

# ─── TRIGGER FILE WATCHER (emits image_update when either heatmap changes) ─────
WATCH_FILES = [
    r"C:\Users\Bhavana\Documents\Hardware 3\z_Target heat_PNG_Outpumap_Colourt\target_heatmap.png",
    r"C:\Users\Bhavana\Documents\Hardware 3\z_Target heatmap_Colour_PNG_Output\progress_heatmap.png",
]

def trigger_watcher():
    mtimes = {f: 0.0 for f in WATCH_FILES}
    while True:
        try:
            for path in WATCH_FILES:
                if os.path.exists(path):
                    mtime = os.path.getmtime(path)
                    if mtimes[path] and mtime != mtimes[path]:
                        socketio.emit('image_update', {})
                        print(f"[Trigger] {os.path.basename(path)} changed — image_update emitted")
                    mtimes[path] = mtime
        except Exception as e:
            print(f"[Trigger] Error: {e}")
        _time.sleep(1)

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

@socketio.on('request_state')
def on_request_state():
    emit('state_sync', session.to_dict())

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
    threading.Thread(target=udp_listener,   daemon=True).start()
    threading.Thread(target=session_timer,  daemon=True).start()
    threading.Thread(target=trigger_watcher, daemon=True).start()
    print("[Clay Create] Server     →  http://0.0.0.0:5000")
    print("[Clay Create] Projection →  http://0.0.0.0:5000/projection")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
