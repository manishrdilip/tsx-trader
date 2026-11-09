"""Copy the India bot's results to GitHub (results/india_vmm_live/ on main) so the
evening review can read them. Uses GH_TOKEN from .env (fine-grained token, this repo,
Contents: Read and write). Does nothing if GH_TOKEN is empty. Never touches the server's git checkout."""
import base64
import hashlib
import os

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "results", "india_vmm")
REPO = os.environ.get("GH_REPO", "manishrdilip/tsx-trader")
FILES = ["state.json", "report.md", "log.jsonl", "alerts.json"]
SKIP_KEYS = ()  # nothing secret is stored in these files


def blob_sha(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def main():
    token = os.environ.get("GH_TOKEN", "").strip()
    if not token:
        print("publish: GH_TOKEN not set, skipped")
        return
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    for name in FILES:
        path = os.path.join(OUT, name)
        if not os.path.exists(path):
            continue
        data = open(path, "rb").read()
        url = f"https://api.github.com/repos/{REPO}/contents/results/india_vmm_live/{name}"
        r = requests.get(url, headers=h, params={"ref": "main"}, timeout=20)
        sha = r.json().get("sha") if r.status_code == 200 else None
        if sha == blob_sha(data):
            continue
        body = {"message": f"India VMM live results: {name}", "branch": "main",
                "content": base64.b64encode(data).decode()}
        if sha:
            body["sha"] = sha
        r = requests.put(url, headers=h, json=body, timeout=30)
        print("publish", name, r.status_code)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(HERE))
    import local_env  # noqa: F401
    main()
