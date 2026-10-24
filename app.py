import os
import uuid
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pexpect
from flask import Flask, redirect, render_template_string, request

app = Flask(__name__)

JOB_LOCK = Lock()
TERMINAL_JOBS = {}
EXECUTOR = ThreadPoolExecutor(max_workers=10)

PANELS = [
    {"name": "Terminal 1", "prefix": "terminal_1"},
    {"name": "Terminal 2", "prefix": "terminal_2"},
    {"name": "Terminal 3", "prefix": "terminal_3"},
]


def parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def run_terminal_sequence(config):
    job_id = uuid.uuid4().hex

    with JOB_LOCK:
        TERMINAL_JOBS[job_id] = {
            "job_id": job_id,
            "terminal": config["name"],
            "status": "running",
            "log": [f"Starting {config['name']}"],
        }

    child = None
    status = "completed"
    error = None

    try:
        child = pexpect.spawn("/bin/bash", encoding="utf-8", timeout=30)
        child.delaybeforesend = 0

        child.sendline("sudo rst")
        time.sleep(4)

        child.sendline("go")
        time.sleep(4)

        child.sendline(config["level"])
        time.sleep(3)

        child.sendline(str(config["thread_count"]))
        time.sleep(2)

        child.sendline(str(config["sleep_value"]))

        if config["level"] == "l4":
            child.sendline(config["method"])

        child.sendline(str(config["interval"]))
        time.sleep(3)

        child.sendline("run")
        time.sleep(2)

        child.sendline("y")
        time.sleep(2)

        with JOB_LOCK:
            TERMINAL_JOBS[job_id]["log"].append("Command sequence completed")

    except Exception as exc:
        status = "failed"
        error = str(exc)
        with JOB_LOCK:
            TERMINAL_JOBS[job_id]["log"].append(f"Error: {exc}")
            TERMINAL_JOBS[job_id]["error"] = str(exc)
            TERMINAL_JOBS[job_id]["traceback"] = traceback.format_exc()

    finally:
        if child is not None:
            try:
                if child.isalive():
                    child.sendline("exit")
            except Exception:
                pass
            try:
                child.close(force=True)
            except Exception:
                pass

        with JOB_LOCK:
            TERMINAL_JOBS[job_id]["status"] = status
            TERMINAL_JOBS[job_id]["error"] = error
            TERMINAL_JOBS[job_id]["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    return {"status": status, "terminal": config["name"], "error": error}


@app.route("/", methods=["GET"])
def index():
    recent_jobs = list(TERMINAL_JOBS.values())[-10:]
    return render_template_string(TEMPLATE, panels=PANELS, jobs=recent_jobs)


@app.route("/run-all", methods=["POST"])
def run_all():
    for panel in PANELS:
        prefix = panel["prefix"]

        payload = {
            "name": panel["name"],
            "level": request.form.get(f"{prefix}_level", "l7"),
            "thread_count": parse_int(request.form.get(f"{prefix}_thread_count"), 1),
            "sleep_value": parse_int(request.form.get(f"{prefix}_sleep_value"), 1),
            "method": request.form.get(f"{prefix}_method", "default"),
            "interval": parse_int(request.form.get(f"{prefix}_interval"), 1),
        }

        EXECUTOR.submit(run_terminal_sequence, payload)

    return redirect("/")


TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Parallel Terminal Dashboard</title>
  <style>
    :root {
      --bg: #0f172a;
      --panel: #111827;
      --surface: #1f2937;
      --border: #374151;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --primary: #22c55e;
      --primary-dark: #16a34a;
      --warning: #f59e0b;
      --danger: #ef4444;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: linear-gradient(180deg, #020817 0%, #0f172a 100%);
      color: var(--text);
    }

    .container {
      max-width: 1400px;
      margin: 0 auto;
      padding: 32px 20px 80px;
    }

    h1 {
      font-size: 2.2rem;
      margin: 0 0 24px;
      text-align: center;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(260px, 1fr));
      gap: 20px;
      margin-bottom: 24px;
    }

    .panel {
      background: rgba(17, 24, 39, 0.96);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
    }

    .panel h2 {
      margin-top: 0;
      margin-bottom: 16px;
      font-size: 1.4rem;
      color: #f8fafc;
    }

    .field {
      margin-bottom: 16px;
    }

    .field label {
      display: block;
      font-size: 0.9rem;
      margin-bottom: 8px;
      color: var(--muted);
    }

    .field input, .field select {
      width: 100%;
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 1rem;
    }

    .primary-btn {
      display: block;
      width: 100%;
      border: none;
      border-radius: 12px;
      background: linear-gradient(135deg, var(--primary), var(--primary-dark));
      color: white;
      font-weight: 700;
      font-size: 1.2rem;
      padding: 16px 20px;
      cursor: pointer;
      transition: transform 0.15s ease, opacity 0.15s ease;
      box-shadow: 0 12px 25px rgba(34, 197, 94, 0.35);
    }

    .primary-btn:hover {
      transform: translateY(-1px);
      opacity: 0.96;
    }

    .status-box {
      background: rgba(17, 24, 39, 0.8);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      margin-top: 20px;
    }

    .status-box h3 {
      margin-top: 0;
    }

    ul {
      padding-left: 18px;
      margin-bottom: 0;
    }

    .running { color: var(--warning); }
    .completed { color: var(--primary); }
    .failed { color: var(--danger); }
    
    @media (max-width: 980px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Parallel Terminal Execution Dashboard</h1>

    <form method="POST" action="/run-all">
      <div class="grid">
        {% for panel in panels %}
        <div class="panel">
          <h2>{{ panel.name }}</h2>

          <div class="field">
            <label for="{{ panel.prefix }}_level">Level</label>
            <select id="{{ panel.prefix }}_level" name="{{ panel.prefix }}_level">
              <option value="l7">l7</option>
              <option value="l4">l4</option>
            </select>
          </div>

          <div class="field">
            <label for="{{ panel.prefix }}_thread_count">Thread count</label>
            <input id="{{ panel.prefix }}_thread_count" name="{{ panel.prefix }}_thread_count" type="number" min="1" value="1">
          </div>

          <div class="field">
            <label for="{{ panel.prefix }}_sleep_value">Sleep value</label>
            <input id="{{ panel.prefix }}_sleep_value" name="{{ panel.prefix }}_sleep_value" type="number" min="1" value="1">
          </div>

          <div class="field">
            <label for="{{ panel.prefix }}_method">Method</label>
            <select id="{{ panel.prefix }}_method" name="{{ panel.prefix }}_method">
              <option value="default">default</option>
              <option value="fast">fast</option>
              <option value="safe">safe</option>
            </select>
          </div>

          <div class="field">
            <label for="{{ panel.prefix }}_interval">Interval</label>
            <input id="{{ panel.prefix }}_interval" name="{{ panel.prefix }}_interval" type="number" min="1" value="1">
          </div>
        </div>
        {% endfor %}
      </div>

      <button class="primary-btn" type="submit">RUN ALL 3 SIMULTANEOUSLY</button>
    </form>

    <div class="status-box">
      <h3>Execution status</h3>
      {% if jobs %}
      <ul>
        {% for job in jobs %}
        <li>
          <strong>{{ job.terminal }}</strong> —
          <span class="{{ job.status }}">{{ job.status }}</span>
          {% if job.error %}
            <br><small>{{ job.error }}</small>
          {% endif %}
        </li>
        {% endfor %}
      </ul>
      {% else %}
      <p>No jobs have started yet.</p>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
