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

            data = child.read_nonblocking(size=8192, timeout=0.2)
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


def run_terminal_sequence(terminal_id, payload):
    child = get_or_create_terminal(terminal_id)
    emit(
        "terminal_output",
        {
            "terminal_id": terminal_id,
            "data": f"\n[Automation started on {terminal_id}] [IP={payload.get('ip', '')}] \n",
        },
        room=terminal_id,
    )

    try:
        child.sendline("sudo rst")
        time.sleep(4)

        child.sendline("go")
        time.sleep(4)

        child.sendline(payload["level"])
        time.sleep(3)

        child.sendline(str(payload["threads"]))
        time.sleep(2)

        child.sendline(str(payload["sleep"]))

        if payload["level"] == "l4":
            child.sendline(payload.get("method", "default"))

        child.sendline(str(payload["interval"]))
        time.sleep(3)

        child.sendline("run")
        time.sleep(2)

        child.sendline("y")
        time.sleep(2)

        emit(
            "terminal_output",
            {"terminal_id": terminal_id, "data": f"\n[Automation finished on {terminal_id}]\n"},
            room=terminal_id,
        )

    except Exception as exc:
        emit(
            "terminal_output",
            {"terminal_id": terminal_id, "data": f"\n[Automation error on {terminal_id}: {exc}]\n"},
            room=terminal_id,
        )


def trigger_all_automations(payload):
    for terminal_id in TERMINAL_IDS:
        EXECUTOR.submit(run_terminal_sequence, terminal_id, payload)


@app.route("/")
def index():
    return render_template_string(TEMPLATE)


@app.route("/run-all", methods=["POST"])
def run_all():
    payload = {
        "ip": request.form.get("ip", ""),
        "level": request.form.get("level", "l7"),
        "method": request.form.get("method", "default"),
        "threads": int(request.form.get("threads", 1)),
        "interval": int(request.form.get("interval", 1)),
        "sleep": int(request.form.get("sleep", 1)),
    }
    trigger_all_automations(payload)
    return jsonify({"status": "queued", "message": "Automation started across all 3 terminals."})


TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mobile Terminal Dashboard</title>
  <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
  <style>
    :root {
      --bg: #07111d;
      --panel: #111c2d;
      --panel-2: #16273d;
      --border: #294160;
      --text: #eaf2ff;
      --muted: #a8bddb;
      --green: #2ed27a;
      --blue: #4aa7ff;
      --shadow: rgba(0,0,0,0.35);
    }

    * { box-sizing: border-box; }

    html, body {
      margin: 0;
      padding: 0;
      font-family: Arial, sans-serif;
      background: linear-gradient(180deg, #050d16 0%, var(--bg) 100%);
      color: var(--text);
    }

    body {
      min-height: 100vh;
    }

    .container {
      width: min(1500px, 100%);
      margin: 0 auto;
      padding: 18px 14px 40px;
    }

    .topbar {
      background: rgba(17, 28, 45, 0.92);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
      box-shadow: 0 10px 28px var(--shadow);
      margin-bottom: 16px;
    }

    .controls {
      display: grid;
      grid-template-columns: repeat(7, minmax(110px, 1fr));
      gap: 10px;
      align-items: end;
    }

    .control-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }

    input, select, button, textarea {
      width: 100%;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--text);
      padding: 12px 12px;
      font-size: 15px;
    }

    input, select {
      min-height: 46px;
    }

    textarea {
      min-height: 82px;
      resize: vertical;
      font-family: Consolas, Monaco, monospace;
      font-size: 13px;
    }

    button {
      min-height: 46px;
      background: linear-gradient(135deg, var(--green), #1cad66);
      border: none;
      color: #06150d;
      font-weight: 700;
      font-size: 15px;
      cursor: pointer;
      box-shadow: 0 12px 24px rgba(46, 210, 122, 0.3);
    }

    .terminal-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(260px, 1fr));
      gap: 16px;
    }

    .terminal {
      background: rgba(17, 28, 45, 0.92);
      border: 1px solid var(--border);
      border-radius: 16px;
      overflow: hidden;
      min-height: 500px;
      display: flex;
      flex-direction: column;
      box-shadow: 0 10px 24px var(--shadow);
    }

    .terminal-header {
      padding: 12px 14px;
      border-bottom: 1px solid var(--border);
      background: rgba(22, 39, 61, 0.9);
      font-weight: 700;
      letter-spacing: 0.04em;
    }

    .terminal-output {
      flex: 1;
      background: #020b11;
      padding: 12px 12px;
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
      background: rgba(22, 39, 61, 0.9);
    }

    .send-btn {
      margin-top: 10px;
      background: linear-gradient(135deg, var(--blue), #297ad9);
      color: white;
      font-weight: 700;
      box-shadow: 0 12px 22px rgba(74, 167, 255, 0.28);
    }

    @media (max-width: 1100px) {
      .controls {
        grid-template-columns: repeat(2, minmax(140px, 1fr));
      }

      .terminal-grid {
        grid-template-columns: 1fr;
      }

      .terminal {
        min-height: 420px;
      }
    }

    @media (max-width: 520px) {
      .container {
        padding: 12px 10px 30px;
      }

      .controls {
        grid-template-columns: 1fr;
      }

      .topbar {
        padding: 12px;
      }

      button, input, select, textarea {
        font-size: 16px;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <form id="run-all-form" class="topbar">
      <div class="controls">
        <div class="control-group">
          <label for="ip">IP</label>
          <input id="ip" name="ip" type="text" value="127.0.0.1">
        </div>

        <div class="control-group">
          <label for="level">Level</label>
          <select id="level" name="level">
            <option value="l7">l7</option>
            <option value="l4">l4</option>
          </select>
        </div>

        <div class="control-group">
          <label for="method">Method</label>
          <input id="method" name="method" type="text" value="default">
        </div>

        <div class="control-group">
          <label for="threads">Threads</label>
          <input id="threads" name="threads" type="number" min="1" value="1">
        </div>

        <div class="control-group">
          <label for="interval">Interval</label>
          <input id="interval" name="interval" type="number" min="1" value="1">
        </div>

        <div class="control-group">
          <label for="sleep">Sleep</label>
          <input id="sleep" name="sleep" type="number" min="1" value="1">
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
          <textarea id="input-terminal_1" placeholder="Type any Linux command..."></textarea>
          <button class="send-btn" data-terminal-id="terminal_1">Send Command</button>
        </div>
      </div>

      <div class="terminal" data-terminal-id="terminal_2">
        <div class="terminal-header">Terminal 2</div>
        <div class="terminal-output" id="terminal-output-terminal_2"></div>
        <div class="terminal-input-wrap">
          <textarea id="input-terminal_2" placeholder="Type any Linux command..."></textarea>
          <button class="send-btn" data-terminal-id="terminal_2">Send Command</button>
        </div>
      </div>

      <div class="terminal" data-terminal-id="terminal_3">
        <div class="terminal-header">Terminal 3</div>
        <div class="terminal-output" id="terminal-output-terminal_3"></div>
        <div class="terminal-input-wrap">
          <textarea id="input-terminal_3" placeholder="Type any Linux command..."></textarea>
          <button class="send-btn" data-terminal-id="terminal_3">Send Command</button>
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
