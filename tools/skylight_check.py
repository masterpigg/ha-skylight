"""Read-only Skylight API check (stdlib only).

  python skylight_check.py start             -> prints the Skylight sign-in URL (PKCE)
  python skylight_check.py finish <url|code> -> trades the one-time code for tokens, runs GET checks
  python skylight_check.py check             -> re-runs GET checks with saved tokens (refreshes if needed)

Sign-in details follow the community fix in TheEagleByte/skylight-mcp PR #48.
Only GET requests are made against Skylight data. Set SKYLIGHT_TZ to an IANA time
zone name for calendar queries (default UTC). Tokens are saved next to this
script in skylight_tokens.json and never printed.
"""
import base64, datetime as dt, hashlib, json, os, secrets, sys, time
import urllib.parse, urllib.request, urllib.error

BASE = "https://app.ourskylight.com"
API_VERSION = "2026-10-15"
CLIENT_ID = "skylight-mobile"
REDIRECT = "https://ourskylight.com/welcome"
SCOPE = "everything"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "pkce_state.json")
TOKEN_FILE = os.path.join(HERE, "skylight_tokens.json")
UA = "ha-skylight-check/0.1"
TIMEZONE = os.environ.get("SKYLIGHT_TZ", "UTC")  # IANA name, e.g. America/Chicago

def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def http(method, path, token=None, form=None, params=None):
    url = BASE + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    data = urllib.parse.urlencode(form).encode() if form else None
    h = {"Accept": "application/json", "Skylight-Api-Version": API_VERSION, "User-Agent": UA}
    if form: h["Content-Type"] = "application/x-www-form-urlencoded"
    if token: h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode(errors="ignore")
        return e.code, body

def save_tokens(resp):
    tok = {"access_token": resp["access_token"], "refresh_token": resp.get("refresh_token"),
           "expires_at": (resp.get("created_at") or int(time.time())) + int(resp.get("expires_in", 0))}
    with open(TOKEN_FILE, "w") as f: json.dump(tok, f)
    return tok

def start():
    verifier = b64u(secrets.token_bytes(64))
    challenge = b64u(hashlib.sha256(verifier.encode()).digest())
    state = b64u(secrets.token_bytes(16))
    with open(STATE_FILE, "w") as f: json.dump({"verifier": verifier, "state": state}, f)
    print(BASE + "/oauth/authorize?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": CLIENT_ID, "redirect_uri": REDIRECT, "scope": SCOPE,
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state}))

def finish(arg):
    st = json.load(open(STATE_FILE))
    arg = arg.strip()
    if "code=" in arg:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(arg).query or arg.split("?", 1)[-1])
        if q.get("state", [st["state"]])[0] != st["state"]:
            sys.exit("state mismatch: that code is from a different sign-in attempt")
        code = q["code"][0]
    else:
        code = arg
    s, r = http("POST", "/oauth/token", form={"grant_type": "authorization_code", "client_id": CLIENT_ID,
               "code": code, "code_verifier": st["verifier"], "redirect_uri": REDIRECT, "scope": SCOPE})
    if s != 200: sys.exit(f"token exchange failed: HTTP {s} {r}")
    tok = save_tokens(r)
    os.remove(STATE_FILE)
    print(f"token exchange OK (access token valid {r.get('expires_in')}s, refresh token: {'yes' if tok['refresh_token'] else 'NO'})")
    check()

def token():
    tok = json.load(open(TOKEN_FILE))
    if time.time() > tok["expires_at"] - 60 and tok.get("refresh_token"):
        s, r = http("POST", "/oauth/token", form={"grant_type": "refresh_token", "client_id": CLIENT_ID,
                   "refresh_token": tok["refresh_token"]})
        if s != 200: sys.exit(f"refresh failed: HTTP {s} {r}")
        r.setdefault("refresh_token", tok["refresh_token"])
        tok = save_tokens(r); print("refreshed access token OK")
    return tok["access_token"]

def summarize(name, s, body, title_keys=("title", "name", "summary", "label")):
    if s != 200:
        print(f"  {name:<22} HTTP {s}  {str(body)[:120]}"); return []
    data = body.get("data") if isinstance(body, dict) else body
    items = data if isinstance(data, list) else [data] if data else []
    titles = []
    for it in items[:4]:
        a = (it or {}).get("attributes", {}) if isinstance(it, dict) else {}
        t = next((a[k] for k in title_keys if a.get(k)), None)
        if t: titles.append(str(t)[:30])
    keys = sorted(((items[0] or {}).get("attributes") or {}).keys())[:10] if items and isinstance(items[0], dict) else []
    print(f"  {name:<22} OK  {len(items):>3} items  e.g. {titles}  fields: {keys}")
    return items

def check():
    t = token()
    today = dt.date.today()
    s, b = http("GET", "/api/user", t); summarize("user", s, b, ("name", "first_name"))
    s, b = http("GET", "/api/frames", t); frames = summarize("frames", s, b)
    for fr in frames:
        fid = fr["id"]; print(f"frame {fid}:")
        tests = [
            ("chores (this week)", f"/api/frames/{fid}/chores", {"after": today.isoformat(), "before": (today + dt.timedelta(days=7)).isoformat(), "include_late": "true"}),
            ("lists", f"/api/frames/{fid}/lists", None),
            ("calendar (2 weeks)", f"/api/frames/{fid}/calendar_events", {"date_min": today.isoformat(), "date_max": (today + dt.timedelta(days=14)).isoformat(), "timezone": TIMEZONE}),
            ("categories (people)", f"/api/frames/{fid}/categories", None),
            ("meal sittings", f"/api/frames/{fid}/meals/sittings", {"date_min": today.isoformat(), "date_max": (today + dt.timedelta(days=14)).isoformat()}),
            ("rewards", f"/api/frames/{fid}/rewards", None),
            ("reward points", f"/api/frames/{fid}/reward_points", None),
            ("task box", f"/api/frames/{fid}/task_box/items", None),
        ]
        for name, path, params in tests:
            s, b = http("GET", path, t, params=params); summarize(name, s, b)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    {"start": start, "check": check}.get(cmd, lambda: finish(" ".join(sys.argv[2:])))()
