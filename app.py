import json
import threading
import time
from collections import deque

import pexpect
from flask import Flask, request, render_template_string

app = Flask(__name__)

MAX_LOG_SIZE = 200
log_buffer = deque(maxlen=MAX_LOG_SIZE)
log_lock = threading.Lock()

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Terminal Control Dashboard</title>
    <style>
        :root {
            --bg: #0b1020;
            --panel: #121a2d;
            --panel-alt: #172338;
            --border: #22304d;
            --text: #ecf3ff;
            --muted: #9cadc8;
            --primary: #6aa8ff;
            --primary-strong: #3a7af7;
            --accent: #1dd1a1;
            --danger: #ff6b6b;
            --shadow: rgba(0, 0, 0, 0.35);
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, Helvetica, sans-serif;
            background: linear-gradient(180deg, #0a101d 0%, #0d1426 100%);
            color: var(--text);
        }
        .container {
            max-width: 1500px;
            margin: 24px auto;
            padding: 0 18px 24px;
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
            padding: 8px 0;
        }
        .title {
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 0.04em;
        }
        .status-pill {
            border: 1px solid var(--border);
            background: rgba(26, 37, 60, 0.8);
            padding: 8px 14px;
            border-radius: 999px;
            color: var(--muted);
            font-size: 12px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(3, minmax(280px, 1fr));
            gap: 18px;
        }
        .panel {
            background: linear-gradient(180deg, var(--panel) 0%, var(--panel-alt) 100%);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 18px 18px 16px;
            box-shadow: 0 14px 28px var(--shadow);
        }
        .panel h2 {
            margin: 0 0 18px;
            font-size: 20px;
            color: var(--text);
        }
        .field {
            margin-bottom: 14px;
        }
        .field label {
            display: block;
            font-size: 12px;
            color: var(--muted);
            margin-bottom: 8px;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .field input,
        .field select {
            width: 100%;
            border: 1px solid var(--border);
            background: rgba(10, 15, 28, 0.9);
            color: var(--text);
            border-radius: 10px;
            height: 42px;
            padding: 8px 12px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }
        .field input:focus,
        .field select:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(106, 168, 255, 0.18);
        }
        .footer {
            margin-top: 24px;
            display: flex;
            justify-content: center;
        }
        .run-all-btn {
            width: min(760px, 100%);
            border: none;
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-strong) 100%);
            color: white;
            font-weight: 700;
            letter-spacing: 0.06em;
            font-size: 18px;
            padding: 16px 28px;
            border-radius: 14px;
            cursor: pointer;
            box-shadow: 0 20px 30px rgba(58, 122, 247, 0.35);
            transition: transform 0.15s ease, filter 0.2s ease;
        }
        .run-all-btn:hover {
            filter: brightness(1.08);
            transform: translateY(-1px);
        }
        .run-all-btn:active {
            transform: translateY(0);
        }
        .log-box {
            margin-top: 22px;
            background: rgba(8, 12, 21, 0.9);
            border: 1px solid var(--border);
            border-radius: 14px;
            min-height: 220px;
            max-height: 260px;
            overflow: auto;
            padding: 12px 14px;
            font-family: "Consolas", "SFMono-Regular", monospace;
            font-size: 13px;
            color: #d9eeff;
            line-height: 1.6;
            white-space: pre-wrap;
        }
        .log-entry {
            border-bottom: 1px solid rgba(255,255,255,0.03);
            padding-bottom: 8px;
            margin-bottom: 8px;
        }
        .log-entry:last-child {
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }
        @media (max-width: 980px) {
            .dashboard {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">Terminal Execution Dashboard</div>
            <div class="status-pill">Safe Lab Automation</div>
        </div>

        <form id="terminal-form">
            <div class="dashboard">
                {% for idx in [1,2,3] %}
                <div class="panel">
                    <h2>Terminal {{ idx }}</h2>
                    <div class="field">
                        <label for="ip_{{ idx }}">IP Address</label>
                        <input id="ip_{{ idx }}" name="ip_{{ idx }}" type="text" value="10.0.0.{{ idx }}" placeholder="192.168.1.10" />
                    </div>
                    <div class="field">
                        <label for="level_{{ idx }}">Level</label>
                        <select id="level_{{ idx }}" name="level_{{ idx }}">
                            <option value="l7">l7</option>
                            <option value="l4">l4</option>
                        </select>
                    </div>
                    <div class="field">
                        <label for="method_{{ idx }}">Method</label>
                        <input id="method_{{ idx }}" name="method_{{ idx }}" type="text" value="GET" placeholder="GET" />
                    </div>
                    <div class="field">
                        <label for="threads_{{ idx }}">Threads</label>
                        <input id="threads_{{ idx }}" name="threads_{{ idx }}" type="number" min="1" max="1000" value="20" />
                    </div>
                    <div class="field">
                        <label for="interval_{{ idx }}">Interval</label>
                        <input id="interval_{{ idx }}" name="interval_{{ idx }}" type="number" min="1" max="10000" value="10" />
                    </div>
                    <div class="field">
                        <label for="sleep_{{ idx }}">Sleep Time</label>
                        <input id="sleep_{{ idx }}" name="sleep_{{ idx }}" type="number" min="0" max="600" value="5" />
                    </div>
                </div>
                {% endfor %}
            </div>

            <div class="footer">
                <button type="submit" class="run-all-btn">RUN ALL 3 SIMULTANEOUSLY</button>
            </div>
        </form>

        <div id="log-box" class="log-box" aria-live="polite"></div>
    </div>

    <script>
        const form = document.getElementById('terminal-form');
        const logBox = document.getElementById('log-box');

        function appendLog(message) {
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.textContent = message;
            logBox.appendChild(entry);
            logBox.scrollTop = logBox.scrollHeight;
        }

        function resetLog() {
            logBox.innerHTML = '';
            appendLog('Waiting for sessions...');
        }

        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            resetLog();

            const payload = {};
            for (let idx = 1; idx <= 3; idx += 1) {
                payload[idx] = {
                    ip: document.getElementById(`ip_${idx}`).value,
                    level: document.getElementById(`level_${idx}`).value,
                    method: document.getElementById(`method_${idx}`).value,
                    threads: Number(document.getElementById(`threads_${idx}`).value),
                    interval: Number(document.getElementById(`interval_${idx}`).value),
                    sleep: Number(document.getElementById(`sleep_${idx}`).value),
                };
            }

            appendLog('Submitting 3 terminal jobs...');

            try {
                const response = await fetch('/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (data.ok) {
                    appendLog('All terminal jobs started successfully.');
                } else {
                    appendLog(`Request error: ${data.error || 'Unknown error'}`);
                }
            } catch (error) {
                appendLog(`Client error: ${error.message}`);
            }
        });
    </script>
</body>
</html>
"""


def append_log(message):
    with log_lock:
        log_buffer.append(f"[{time.strftime('%H:%M:%S')}] {message}")


APP_LOGS = []


def safe_terminal_sequence(term_index, config):
    """Run an internal-safe automation sequence in a dedicated bash session.

    This is intentionally non-destructive and demonstrates a controlled terminal workflow.
    Replace the simulated shell commands below with approved internal automation in a
    production environment.
    """
    try:
        append_log(f"Terminal {term_index}: starting safe automation sequence")
        child = pexpect.spawn('/bin/bash', encoding='utf-8', echo=False)
        child.delaybeforesend = 0.1

        # Sequence roughly mirrors the requested flow, but uses harmless commands only.
        child.sendline(f"echo 'Terminal {term_index} initializing'")
        time.sleep(4)

        child.sendline(f"echo 'target={config['ip']}'")
        time.sleep(4)

        child.sendline(f"echo 'level={config['level']}'")
        time.sleep(3)

        child.sendline(f"echo 'threads={config['threads']}'")
        time.sleep(2)

        child.sendline(f"echo 'sleep={config['sleep']}'")
        time.sleep(1)

        if config['level'] == 'l4':
            child.sendline(f"echo 'method={config['method']}'")
            time.sleep(1)

        child.sendline(f"echo 'interval={config['interval']}'")
        time.sleep(3)

        child.sendline(f"echo 'run: Terminal {term_index} ready'")
        time.sleep(2)

        child.sendline(f"echo 'complete: Terminal {term_index} done'")
        time.sleep(1)

        try:
            while True:
                child.read_nonblocking(size=4096, timeout=0.2)
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass

        child.close(force=True)
        append_log(f"Terminal {term_index}: completed successfully")
    except Exception as exc:  # pragma: no cover - runtime safety fallback
        append_log(f"Terminal {term_index}: error: {exc}")


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            payload = request.get_json(force=True, silent=True) or {}
            tasks = []
            for idx in range(1, 4):
                config = payload.get(str(idx), payload.get(idx, {}))
                if not config:
                    return {"ok": False, "error": f"Missing config for terminal {idx}"}, 400

                config = {
                    "ip": str(config.get('ip', '10.0.0.1')),
                    "level": str(config.get('level', 'l7')),
                    "method": str(config.get('method', 'GET')),
                    "threads": int(config.get('threads', 1)),
                    "interval": int(config.get('interval', 1)),
                    "sleep": int(config.get('sleep', 0)),
                }
                tasks.append((idx, config))

            append_log('Launching 3 terminal jobs concurrently')
            threads = []
            for idx, config in tasks:
                t = threading.Thread(target=safe_terminal_sequence, args=(idx, config), daemon=True)
                t.start()
                threads.append(t)

            for t in threads:
                t.join(timeout=0.5)

            return {"ok": True}
        except Exception as exc:  # pragma: no cover - runtime safety fallback
            append_log(f"Request error: {exc}")
            return {"ok": False, "error": str(exc)}, 500

    return render_template_string(HTML)


@app.route('/logs')
def get_logs():
    with log_lock:
        return {"logs": list(log_buffer)}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=False, threaded=True)
