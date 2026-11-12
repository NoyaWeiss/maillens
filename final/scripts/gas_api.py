"""Tiny helper for the Apps Script API using clasp's stored login (~/.clasprc.json)."""
import json, os, pathlib, sys, urllib.parse, urllib.request


def token() -> str:
    rc = json.load(open(os.path.expanduser("~/.clasprc.json")))
    t = rc.get("tokens", {}).get("default", rc.get("token", {}))
    data = urllib.parse.urlencode({"client_id": t["client_id"], "client_secret": t["client_secret"],
                                   "refresh_token": t["refresh_token"], "grant_type": "refresh_token"}).encode()
    return json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data))["access_token"]


def call(method: str, path: str, body=None):
    req = urllib.request.Request("https://script.googleapis.com/v1/" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "create":
        print(call("POST", "projects", {"title": sys.argv[2]})["scriptId"])
    elif cmd == "push":  # push <scriptId> <dir>: uploads appsscript.json + *.js
        d = pathlib.Path(sys.argv[3])
        files = [{"name": "appsscript", "type": "JSON", "source": (d / "appsscript.json").read_text()}]
        files += [{"name": f.stem, "type": "SERVER_JS", "source": f.read_text()} for f in sorted(d.glob("*.js"))]
        call("PUT", f"projects/{sys.argv[2]}/content", {"files": files})
        print("pushed", [f["name"] for f in files])
    elif cmd == "files":
        files = call("GET", f"projects/{sys.argv[2]}/content")["files"]
        print(json.dumps({f["name"]: f["source"] for f in files}))
