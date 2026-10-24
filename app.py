import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import pexpect
from flask import Flask, jsonify, render_template_string, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "render-terminal-secret")

socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*")

TERMINAL_IDS = ["terminal_1", "terminal_2", "terminal_3"]
TERMINAL_SESSIONS = {}
TERMINAL_LOCK = threading.Lock()
EXECUTOR = ThreadPoolExecutor(max_workers=10)


def get_or_create_terminal(terminal_id):
    with TERMINAL_LOCK:
        session = TERMINAL_SESSIONS.get(terminal_id)
        if session is None:
            child = pexpect.spawn("/bin/bash", encoding="utf-8", timeout=0.2)
            child.delaybeforesend = 0
            child.sendline("export TERM=xterm")
            session = {"child": child}
            TERMINAL_SESSIONS[terminal_id] = session

            reader = threading.Thread(target=_terminal_reader, args=(terminal_id,), daemon=True)
            reader.start()
            session["reader_thread"] = reader

        return TERMINAL_SESSIONS[terminal_id]["child"]


def _terminal_reader(terminal_id):
    child = TERMINAL_SESSIONS[terminal_id]["child"]

    while True:
        try:
            if not child.isalive():
                break

            data = child.read_nonblocking(size=16384, timeout=0.2)
            if data:
                socketio.emit(
                    "terminal_output",
                    {"terminal_id": terminal_id, "data": data},
                    namespace="/",
                    room=terminal_id,
                )
        except pexpect.TIMEOUT:
            pass
        except pexpect.EOF:
            break
        except Exception:
            break
        time.sleep(0.05)


@socketio.on("join_terminal")
def handle_join_terminal(data):
    terminal_id = data.get("terminal_id", "terminal_1")
    join_room(terminal_id)
    get_or_create_terminal(terminal_id)
    emit(
        "terminal_output",
        {"terminal_id": terminal_id, "data": f"\n[Connected to {terminal_id}]\n"},
        room=terminal_id,
    )


@socketio.on("terminal_input")
def handle_terminal_input(data):
    terminal_id = data.get("terminal_id", "terminal_1")
    text = data.get("input", "")
    child = get_or_create_terminal(terminal_id)

    if child and child.isalive():
        child.send(text)
        emit("terminal_output", {"terminal_id": terminal_id, "data": text}, room=terminal_id)


@socketio.on("clear_terminal")
def handle_clear_terminal(data):
    terminal_id = data.get("terminal_id", "terminal_1")
    session = TERMINAL_SESSIONS.get(terminal_id)
    if session and session["child"].isalive():
        session["child"].send("clear\r")


def run_command_in_terminal(terminal_id, command):
    child = get_or_create_terminal(terminal_id)
    emit(
        "terminal_output",
        {"terminal_id": terminal_id, "data": f"\n[Executing in {terminal_id}] {command}\n"},
        room=terminal_id,
    )
    try:
        child.sendline(command)
    except Exception as exc:
        emit(
            "terminal_output",
            {"terminal_id": terminal_id, "data": f"\n[Command error in {terminal_id}: {exc}]\n"},
            room=terminal_id,
        )


@app.route("/")
def index():
    return render_template_string(TEMPLATE)


@app.route("/run-all", methods=["POST"])
def run_all():
    target_ip = request.form.get("ip", "").strip()
    threads = request.form.get("threads", "1").strip()

    if not target_ip:
        return jsonify({"status": "error", "message": "IP address is required."}), 400

    command = f"python3 go.py -s {target_ip} -t {threads}"

    for terminal_id in TERMINAL_IDS:
        EXECUTOR.submit(run_command_in_terminal, terminal_id, command)

    return jsonify({"status": "queued", "message": f"Started across all terminals: {command}"})


TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Mobile Terminal Dashboard</title>
  <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
  <style>
    :root {
      --bg: #08131d;
      --panel: #101d2d;
      --panel-2: #162b40;
      --border: #294666;
      --text: #edf6ff;
      --muted: #a9c3df;
      --accent: #3ad18f;
      --accent-2: #4ea2ff;
      --shadow: rgba(0,0,0,0.35);
    }

    * { box-sizing: border-box; }

    html, body {
      margin: 0;
      padding: 0;
      font-family: Arial, sans-serif;
      background: linear-gradient(180deg, #050d15 0%, var(--bg) 100%);
      color: var(--text);
      min-height: 100%;
    }

    body {
      min-height: 100vh;
    }

    .container {
      width: min(1400px, 100%);
      margin: 0 auto;
      padding: 14px 12px 36px;
    }

    .topbar {
      background: rgba(16, 29, 45, 0.96);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 12px 30px var(--shadow);
      padding: 14px;
      margin-bottom: 16px;
    }

    .controls {
      display: grid;
      grid-template-columns: repeat(3, minmax(140px, 1fr));
      gap: 12px;
      align-items: end;
    }

    .control-group {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }

    input, button {
      width: 100%;
      min-height: 48px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--text);
      padding: 12px 14px;
      font-size: 16px;
    }

    button {
      background: linear-gradient(135deg, var(--accent), #1ca96a);
      border: none;
      color: #07160d;
      font-weight: 700;
      box-shadow: 0 12px 24px rgba(58, 209, 143, 0.25);
      cursor: pointer;
    }

    .terminal-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(260px, 1fr));
      gap: 16px;
    }

    .terminal {
      background: rgba(16, 29, 45, 0.96);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 10px 24px var(--shadow);
      overflow: hidden;
      min-height: 480px;
      display: flex;
      flex-direction: column;
    }

    .terminal-header {
      padding: 12px 14px;
      border-bottom: 1px solid var(--border);
      background: rgba(20, 38, 58, 0.9);
      font-weight: 700;
      letter-spacing: 0.04em;
    }

    .terminal-output {
      flex: 1;
      background: #02090d;
      padding: 12px;
      overflow: auto;
      font-family: Consolas, Monaco, monospace;
      font-size: 12.5px;
      line-height: 1.5;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .terminal-input-wrap {
      padding: 12px;
      border-top: 1px solid var(--border);
      background: rgba(20, 38, 58, 0.9);
    }

    textarea {
      width: 100%;
      min-height: 78px;
      resize: vertical;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: #0d1723;
      color: var(--text);
      padding: 10px 12px;
      font-family: Consolas, Monaco, monospace;
      font-size: 14px;
    }

    .send-btn {
      margin-top: 10px;
      background: linear-gradient(135deg, var(--accent-2), #2d78d8);
      color: white;
      border: none;
      box-shadow: 0 12px 22px rgba(78, 162, 255, 0.28);
    }

    @media (max-width: 900px) {
      .controls {
        grid-template-columns: 1fr;
      }

      .terminal-grid {
        grid-template-columns: 1fr;
      }

      .terminal {
        min-height: 420px;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <form id="run-all-form" class="topbar">
      <div class="controls">
        <div class="control-group">
          <label for="ip">Target IP Address</label>
          <input id="ip" name="ip" type="text" value="127.0.0.1" placeholder="127.0.0.1">
        </div>

        <div class="control-group">
          <label for="threads">Threads</label>
          <input id="threads" name="threads" type="number" min="1" value="1">
        </div>

        <div class="control-group">
          <label>&nbsp;</label>
          <button type="submit">RUN ALL 3 SIMULTANEOUSLY</button>
        </div>
      </div>
    </form>

    <div class="terminal-grid">
      <div class="terminal" data-terminal-id="terminal_1">
        <div class="terminal-header">Terminal 1</div>
        <div class="terminal-output" id="terminal-output-terminal_1"></div>
        <div class="terminal-input-wrap">
          <textarea id="input-terminal_1" placeholder="Type any Linux command here..."></textarea>
          <button class="send-btn" data-terminal-id="terminal_1">Send</button>
        </div>
      </div>

      <div class="terminal" data-terminal-id="terminal_2">
        <div class="terminal-header">Terminal 2</div>
        <div class="terminal-output" id="terminal-output-terminal_2"></div>
        <div class="terminal-input-wrap">
          <textarea id="input-terminal_2" placeholder="Type any Linux command here..."></textarea>
          <button class="send-btn" data-terminal-id="terminal_2">Send</button>
        </div>
      </div>

      <div class="terminal" data-terminal-id="terminal_3">
        <div class="terminal-header">Terminal 3</div>
        <div class="terminal-output" id="terminal-output-terminal_3"></div>
        <div class="terminal-input-wrap">
          <textarea id="input-terminal_3" placeholder="Type any Linux command here..."></textarea>
          <button class="send-btn" data-terminal-id="terminal_3">Send</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    const socket = io();

    function appendOutput(terminalId, data) {
      const out = document.getElementById("terminal-output-" + terminalId);
      if (out) {
        out.textContent += data;
        out.scrollTop = out.scrollHeight;
      }
    }

    socket.on("connect", () => {
      ["terminal_1", "terminal_2", "terminal_3"].forEach(id => {
        socket.emit("join_terminal", { terminal_id: id });
      });
    });

    socket.on("terminal_output", ({ terminal_id, data }) => {
      appendOutput(terminal_id, data);
    });

    function sendManualCommand(terminalId) {
      const textarea = document.getElementById("input-" + terminalId);
      const value = (textarea.value || "").trim();
      if (!value) return;

      const payload = value + "\\n";
      textarea.value = "";
      socket.emit("terminal_input", { terminal_id: terminalId, input: payload });
    }

    document.querySelectorAll(".send-btn").forEach(button => {
      button.addEventListener("click", () => {
        sendManualCommand(button.dataset.terminalId);
      });
    });

    document.querySelectorAll("textarea").forEach(textarea => {
      textarea.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
          event.preventDefault();
          const terminalId = textarea.id.replace("input-", "");
          sendManualCommand(terminalId);
        }
      });
    });

    document.getElementById("run-all-form").addEventListener("submit", function(e) {
      e.preventDefault();
      const formData = new FormData(this);

      fetch("/run-all", {
        method: "POST",
        body: formData
      })
      .then(response => response.json())
      .then(data => console.log(data))
      .catch(err => console.error(err));
    });
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
