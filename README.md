# MailLens

MailLens is a Gmail add-on that tells you whether the email you just opened is safe. It shows a verdict
(**Low risk, Suspicious, High risk or Inconclusive**), the evidence behind it, and what to do next. A
dashboard (the Security Console) shows your analyzed emails, benchmark results, and how detection works.

**How it decides:** 13 explainable checks look for emails that **contradict themselves** (look-alike domains,
a changed Reply-To, links hiding their destination, hidden text) or **ask for something risky in a suspicious
context** (bank-detail changes, gift cards, passwords or codes). Findings are correlated so nothing is counted
twice; High risk always needs strong or corroborated evidence; missing information never raises the risk.

```
 Gmail ── MailLens add-on ──HTTPS──► Cloudflare tunnel ──► MailLens backend on YOUR computer (Docker)
                                                            ├─ detection engine (stateless, no outbound calls)
                     "View full dashboard" ───────────────► └─ dashboard (per-account history, never email bodies)
```
The backend runs locally. Gmail can only reach public HTTPS addresses, so setup connects it through a free,
temporary Cloudflare tunnel (no Cloudflare account needed).

---

## Install (macOS)

About 15 minutes. Tested on macOS. Linux should work the same way, and on Windows you'd use WSL2 (Ubuntu) with Docker Desktop, but neither has been tested.

### Step 1: Before you start

**Install these yourself** (setup can't install them):

| Tool | How to install | Check it works |
|---|---|---|
| **Docker Desktop** | Download from <https://www.docker.com/products/docker-desktop/>, install it, open it once, and wait until it says it is running | `docker info` shows no error |
| **Apple Command Line Tools** (provides `git`, `python3`, `curl`) | In Terminal: `xcode-select --install`, then click **Install** | `git --version` and `python3 --version` print versions |
| **A Google account for testing** | A separate test account is recommended | — |

**Don't install these:** setup downloads them for you, after asking, into the project's own `.tools/` folder.
They are official builds with verified checksums, and setup needs no administrator password, Homebrew or
`sudo`. If you already have them, setup uses yours.
- Node.js and clasp (Google's Apps Script command-line tool)
- cloudflared (the tunnel)

### Step 2: Download MailLens

Copy and paste into Terminal. This puts MailLens in your home folder (`~/maillens`) and updates it if it's
already there:
```bash
cd ~ && (git clone https://github.com/NoyaWeiss/maillens.git || git -C maillens pull --ff-only)
```

### Step 3: Run setup

```bash
~/maillens/scripts/setup.sh
```
This works from any folder and is safe to run again. Add `--with-demo` to also create 13 synthetic demo emails.

**It does automatically:**
1. checks Docker and the Command Line Tools, and offers to download Node.js, clasp and cloudflared if they are missing
2. creates a private random API key (`backend/.env`, never displayed)
3. builds and starts the backend and dashboard in Docker
4. starts your HTTPS tunnel
5. creates **your own** Apps Script project and uploads the add-on

**It pauses for you** at the Google login (Step 4). When it finishes, you'll see:
```
Automated setup complete. Two manual steps remain (Google requires them):
  1. Open https://script.google.com/home/projects/<your project>/edit
```

### Step 4: Connect Google

| # | What | Who |
|---|---|---|
| 1 | Open <https://script.google.com/home/usersettings> and turn **Google Apps Script API** to **On**. Do this before Step 3; if you forget, setup stops and tells you, so turn it on and re-run Step 3. | **You** |
| 2 | **Google account:** setup shows which Google account MailLens will use and asks you to confirm it. To switch, answer N and sign in with your **test** account in the browser (click "Use another account" if needed), then **Allow**. MailLens uses its own clasp login, separate from any other. | **You** |
| 3 | Create your Apps Script project and upload the MailLens code | Automatic |
| 4 | **Install the add-on:** open the project link setup printed, then **Deploy → Test deployments → Install**, and **Done**. | **You** |
| 5 | **Authorize it in Gmail:** reload Gmail, open any email and click the **MailLens** icon in the right-hand side panel, then **Authorize access**. Google warns "Google hasn't verified this app" (normal for your own private add-on): click **Advanced → Go to MailLens**, then **Allow**. | **You** |

**Permissions MailLens asks for:**
- run inside Gmail and read **only the email you open**
- connect to your own backend
- save its settings
- read mailbox metadata (`gmail.readonly`), used only to recognize people you've emailed and for Scan Inbox

You may untick `gmail.readonly`. MailLens still works without it; only those two features turn off.

### Step 5: Test MailLens

- [ ] With no email open, the MailLens panel says **"Analysis service ready"**.
- [ ] Open any email: a **verdict card** appears (Low risk / Suspicious / High risk / Inconclusive).
- [ ] **View detailed analysis** shows every check and its result.
- [ ] **View full dashboard** opens the Security Console in a new tab, showing the email you analyzed.
- [ ] Optional, with `--with-demo`: open the seeder link setup printed, choose `seedDemoMailbox` and click **Run** once.
  Then the newest "Re: PO 4471 - office supplies" shows **High risk**, "Updated remittance details" shows
  **Suspicious**, and "Invoice #1043 from Brightline Studio" shows **Low risk**.

All checked? MailLens is installed.

> **Not yet verified on a brand-new Google account:** the Google steps were tested on the author's test
> account. If a Google screen looks different, follow Google's prompt.

---

## Start, stop and recover

MailLens runs on your computer, so Gmail analysis works only while your computer is on, Docker is running and
the tunnel is up. The free tunnel gets a **new address every time it restarts** (after a reboot, sleep or network
change), and your add-on only talks to the address it was approved for. Setup is a one-time step; after that:

| When | Run | What it does |
|---|---|---|
| After a restart, or Gmail shows **"Analysis service unavailable"** | `~/maillens/scripts/start.sh` | Starts Docker and the backend, reuses the tunnel if it still works or opens a new one, re-points **your** add-on to the new address, then checks it end to end |
| To stop MailLens | `~/maillens/scripts/stop.sh` | Stops the tunnel and the backend. Your API key, history and add-on are kept |

`start.sh` is safe to run at any time. It takes a few seconds when the tunnel still works, and about 2 minutes
when it opens a new one (a new tunnel address takes that long to come online). It doesn't rebuild anything or ask for a Google login, and it never creates a new Apps Script
project. It only updates the add-on's approved address when the address has changed, and only with the Google
account you confirmed during setup. The add-on's own settings stay locked, so nobody can redirect it from Gmail.
After it says **MailLens is ready**, reload Gmail. No new Google approval is needed.

For an address that never changes, use your own HTTPS endpoint (for example a named Cloudflare tunnel on your
domain): `MAILLENS_TUNNEL_URL=https://your-host ~/maillens/scripts/start.sh`.

---

## Evaluation

Frozen engine, pre-registered synthetic benchmark of 200 emails (100 malicious, 100 legitimate):
**precision 96.9%, recall 63%, F1 0.76, false-positive rate 2%.** The data is synthetic and the categories
are small, so real-world performance may differ. See [docs/EVALUATION_REPORT.md](docs/EVALUATION_REPORT.md).
To reproduce it and run the tests (requires [uv](https://docs.astral.sh/uv/)):
```bash
cd ~/maillens/backend && uv sync && uv run pytest -q && uv run python ../eval/reproduce.py
cd ~/maillens && .tools/bin/node --test addon/tests/ dashboard/tests/     # or: node --test …
```

## Security & limitations

- **Security:**
  - An API key protects every backend call, and the add-on can only reach your own backend.
  - Every value is escaped, and there is no LLM to prompt-inject.
  - Dashboard links are one-time codes with no credentials in the URL, and accounts are isolated.
- **Privacy:** MailLens analyzes the opened email and, when you allow it, uses read access to your mailbox only for
  the recipients of mail you've sent and earlier headers in the open thread. The dashboard keeps subject, sender and
  verdict (never the body) for up to 1 year; **Clear history** removes it.
- **Limitations:**
  - Low risk is not a guarantee.
  - Attachment contents, text in images and domain reputation are not analyzed.
  - Request detection is English only.
  - Runs on your computer: tunnel addresses change when the tunnel restarts; run `scripts/start.sh`.

More: [docs/SECURITY_QA_REPORT.md](docs/SECURITY_QA_REPORT.md) · [docs/TESTING_PLAN.md](docs/TESTING_PLAN.md) ·
[docs/RELIABILITY.md](docs/RELIABILITY.md)

## Troubleshooting

| You see | Do this |
|---|---|
| `npm: command not found` or `brew: command not found` | Nothing to install by hand: setup downloads Node.js, clasp and cloudflared itself (Step 3) |
| `npm ERR! EACCES` | Don't install clasp globally or with sudo; setup installs it in `~/maillens/.tools` |
| `destination path 'maillens' already exists` | Use the Step 2 command; it updates your existing copy instead |
| `no such file or directory: ./scripts/setup.sh` | Run it by its full path: `~/maillens/scripts/setup.sh` |
| "Docker is installed but not running" | Open Docker Desktop, wait until it's running, then re-run the command |
| Setup says to turn on the Apps Script API | Step 4.1, wait about a minute, then re-run setup |
| "Analysis service unavailable" in Gmail | The tunnel stopped (for example after a restart or sleep): run `~/maillens/scripts/start.sh`, then reload Gmail |
| `start.sh`: "the MailLens Google login … doesn't match" | Run `~/maillens/scripts/setup.sh` and confirm your test account |
| No MailLens icon in Gmail | Step 4.4 (install the test deployment), then reload Gmail |
| "Refusing: … belongs to another MailLens checkout" | Another copy uses that port or name: re-run with `MAILLENS_PORT=8788 MAILLENS_CONTAINER=maillens2 MAILLENS_VOLUME=maillens2-data` before the command |
| Backend logs | `docker logs maillens` |

Advanced: use your own HTTPS endpoint with `MAILLENS_TUNNEL_URL=https://… ~/maillens/scripts/setup.sh`, or start
only the backend with `~/maillens/scripts/setup.sh --backend-only`.
