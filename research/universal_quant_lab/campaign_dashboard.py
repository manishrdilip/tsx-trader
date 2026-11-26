"""Local read-only dashboard for a single campaign progress file."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGE = b"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Universal Quant Lab progress</title>
<style>
body{font:16px system-ui;margin:3rem auto;max-width:42rem;padding:0 1rem;background:#111827;color:#f9fafb}
progress{width:100%;height:1.4rem;accent-color:#67e8f9}
dl{display:grid;grid-template-columns:minmax(12rem,1fr) 1fr;gap:.75rem}
dt{color:#cbd5e1}dd{margin:0;font-variant-numeric:tabular-nums}
</style><h1>Universal Quant Lab</h1>
<p id="status" role="status">Waiting for a checkpoint</p>
<label for="engineering">Engineering progress</label><progress id="engineering" value="0" max="1"></progress>
<dl id="stats"></dl>
<script>
const fields = {
 engineering_completed: "Engineering evaluations", engineering_target: "Engineering target",
 official_completed: "Official evaluations", official_target: "Official target",
 distinct_strategies: "Distinct strategies", dataset_count: "Datasets",
 failed_attempts: "Failed attempts", evaluations_per_second: "Evaluations per second",
 parquet_bytes: "Parquet bytes", batch_seconds: "Batch seconds", free_gib: "Free GiB",
 compute_seconds: "Compute seconds", session_wall_seconds: "Session wall seconds",
 compute_evaluations_per_second: "Compute evaluations per second",
 session_evaluations_per_second: "End-to-end evaluations per second",
 updated_utc: "Latest checkpoint (UTC)", memory_available_bytes: "Available RAM bytes",
 max_gpu_celsius: "GPU temperature (C)", cpu_celsius: "CPU temperature (C)"
};
async function refresh() {
 try {
  const response = await fetch("/progress.json", {cache: "no-store"});
  if (!response.ok) throw Error("Checkpoint unavailable");
  const data = await response.json();
  const resources = await fetch("/resources.json", {cache: "no-store"});
  if (resources.ok) {
   const {memory_available_bytes, max_gpu_celsius, cpu_celsius} = await resources.json();
   Object.assign(data, {memory_available_bytes, max_gpu_celsius, cpu_celsius});
  }
  document.getElementById("status").textContent = data.status;
  const progress = document.getElementById("engineering");
  progress.max = data.engineering_target || 1;
  progress.value = data.engineering_completed;
  const stats = document.getElementById("stats");
  stats.replaceChildren();
  for (const [key, label] of Object.entries(fields)) {
   const term = document.createElement("dt");
   const value = document.createElement("dd");
   term.textContent = label;
   value.textContent = data[key]?.toLocaleString() ?? "Unavailable";
   stats.append(term, value);
  }
 } catch { document.getElementById("status").textContent = "Waiting for a checkpoint"; }
 setTimeout(refresh, 1500);
}
refresh();
</script></html>"""


def serve(run, port):
    class Dashboard(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                payload, mime = PAGE, "text/html; charset=utf-8"
            elif self.path in ("/progress.json", "/resources.json"):
                try:
                    payload = (run / self.path[1:]).read_bytes()
                except FileNotFoundError:
                    self.send_error(404)
                    return
                mime = "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_):
            pass

    with ThreadingHTTPServer(("127.0.0.1", port), Dashboard) as server:
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.run, args.port)
