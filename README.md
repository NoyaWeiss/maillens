# MailLens

MailLens is a Gmail add-on that analyzes the email you open and explains its risk. It shows a verdict
(**Low, Suspicious, High or Inconclusive**), a risk index, the evidence behind it, and what to do next.
An optional **Security Console** dashboard shows your analyzed emails, the benchmark results, and how
detection works.

It flags an email when it **contradicts itself** (a look-alike domain, a Reply-To that changed mid-thread,
link text that hides its destination, hidden text aimed at scanners), or when it **asks for something risky
in a suspicious context** (bank-detail changes, gift cards, passwords or codes). A High verdict always needs
strong or corroborated evidence, and missing information never raises the risk.

> Built for the Upwind Security Analyst home assignment. Everything runs on your own machine with your
> own Google account. No cloud hosting or third-party API is needed.

## Architecture

```
 Gmail ── add-on (Apps Script) ──HTTPS──► your tunnel ──► backend (FastAPI, Docker, 127.0.0.1:8787)
            reads the OPEN email,                           ├─ detection engine: stateless, no outbound calls
            renders the verdict card                        └─ /dashboard/: React console + per-account history

 Scan Inbox (optional): dashboard ─ticket─► your own Apps Script web app (runs as you) ─► backend
```

- **Add-on:** extracts the open email (headers, body, attachment names and types, earlier thread headers)
  and renders the result. All analysis happens in the backend, where it is unit-tested.
- **Backend:** the **detection engine is stateless**: it keeps no email and makes no outbound network calls.
  The only stored state is the **dashboard history** (subject, sender and result; never the body), kept
  per account for 1 year in the `maillens-data` Docker volume.
- **Connectivity:** Gmail can only reach HTTPS endpoints, so the local backend is exposed through **your own**
  external HTTPS tunnel (a free Cloudflare quick tunnel). The dashboard is served by the same backend.

## Prerequisites

- **Docker** (Docker Desktop on macOS or Windows)
- **Python 3.9+** (helper scripts only)
- **Node.js 18+** and **clasp**: `npm install -g @google/clasp`
- **cloudflared**: [download](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
- A **Google account** for testing (a dedicated test account is recommended). No Google Cloud project setup
  is needed: Apps Script's default project is enough.

## Install (about 20–30 minutes)

Steps 1–5 are **required**; 6 and 8 are **optional**. Steps marked 👤 need your Google login.

**1. Start the backend**
```bash
git clone https://github.com/NoyaWeiss/maillens.git && cd maillens
./scripts/run-backend-docker.sh
```
This creates `backend/.env` with a new random API key (gitignored), builds the image (including the dashboard)
and starts it on `127.0.0.1:8787`. The output ends with `{"status":"ok"}  <- backend is up`.

**2. Start your HTTPS tunnel**
```bash
./scripts/start-tunnel.sh
```
This prints `https://<random>.trycloudflare.com` and saves it to `.run/url`. Quick-tunnel URLs change on
every restart; after a restart, run `./scripts/push-addon.sh` to re-point the add-on.

**3. 👤 Enable Apps Script and log in to clasp**
1. Turn **Google Apps Script API** to **On** at <https://script.google.com/home/usersettings>.
2. Run `clasp login` and choose your test account.

**4. Create and push the add-on**
```bash
./scripts/setup-addon.sh        # uses the tunnel URL saved in Step 2
```
This creates your Apps Script project (first run only), writes the gitignored `addon/Secrets.js` (your
backend URL and key), restricts the add-on's outbound calls and links to exactly your tunnel host, pushes
it, and prints the editor link.

**5. 👤 Install and authorize**
1. In the editor link: **Deploy → Test deployments → Gmail → Install**.
2. In Gmail, open any email and click the **MailLens** icon in the right-hand panel, then **Authorize access**.
   Google warns "Google hasn't verified this app" (expected for your own unpublished script): choose
   **Advanced → Go to MailLens**, then grant the permissions.

| Scope (all listed in `addon/appsscript.json`) | Why |
|---|---|
| `gmail.addons.execute`, `gmail.addons.current.message.readonly` | Run in Gmail; read only the email you open |
| `script.external_request`, `script.storage` | Call your backend; store settings |
| `gmail.readonly` | Relationship checks (recipients of mail you sent, earlier thread headers) and Scan Inbox |

`gmail.readonly` is in the manifest, but Google's consent screen lets you **decline it**. MailLens still works
without it; relationship checks then show as unavailable, and Scan Inbox is disabled.

**6. Optional: seed the synthetic demo mailbox**
```bash
./scripts/setup-seeder.sh
```
👤 Open the printed link, choose **`seedDemoMailbox`** and click **Run** once. Its only Gmail permission is
*insert*. This adds 13 synthetic emails (`.example` domains).

**7. Verify**
- With no email open, MailLens shows **"Analysis service ready"**.
- With the demo mailbox: the newest "Re: PO 4471 - office supplies" is **High risk**, "Updated remittance details" is
  **Suspicious**, and "Invoice #1043 from Brightline Studio" is **Low risk**.

**8. Optional: Security Console**
- Click **View full dashboard** (Home screen or any result card). It opens in a new tab with a one-time link.
- **Overview:** your analyzed emails over a 1-hour to 1-year window (by received time), with search and each
  email's assessment.
- **Scan Inbox:** analyzes up to 50 of the newest inbox emails in that window. It runs your own Apps Script
  web app as you (created by `push-addon.sh`); Google may ask you to approve once.
- **Also:** Detection Performance and How MailLens Works.

> **Not verified on a brand-new account:** Steps 3–5 were exercised on the author's own test account
> only. If a Google screen differs, follow Google's prompt, then confirm the checklist below.
>
> **Fresh-account checklist:** (1) `clasp login` uses your test account; (2) Install succeeded; (3) you
> authorized MailLens; (4) the Home screen shows "Analysis service ready" and an email shows a verdict;
> (5) optional: the dashboard opens and Scan Inbox completes.

## Evaluation

Frozen engine, pre-registered synthetic benchmark of 200 emails (100 malicious, 100 legitimate):

| Precision | Recall | F1 | False-positive rate | Confusion (TP/FN/FP/TN) |
|---|---|---|---|---|
| 96.9% | 63% | 0.76 | 2% | 63 / 37 / 2 / 98 |

The data is synthetic and the categories are small, so real-world performance may differ. Details and
history: [docs/EVALUATION_REPORT.md](docs/EVALUATION_REPORT.md).

## Tests

```bash
cd backend && uv sync && uv run pytest -q        # 257 tests; needs uv (https://docs.astral.sh/uv/)
uv run python ../eval/reproduce.py               # re-runs the benchmark; prints REPRODUCED
cd .. && node --test addon/tests/ dashboard/tests/   # 87 add-on and dashboard tests
```
Without uv: `pip install -r requirements.txt && pip install pytest httpx && pytest -q` inside `backend/`.

## Security and privacy

- **Untrusted input:** strict schemas and size limits, a bounded HTML parser, and no LLM. Hidden
  "instructions" in an email are themselves a finding.
- **Backend access:** an API key on every call, a rate limit, no outbound network calls, and logs without
  email content.
- **Add-on:** outbound calls and links are allow-listed to exactly your backend host; every value is escaped.
- **Dashboard:** a one-time 2-minute launch code (no tokens or email data in URLs), then a tab-scoped session.
  Accounts are isolated by an HMAC of a private per-user key. **Clear history** deletes stored records.
- **Data:** MailLens analyzes the opened email and, when you allow it, uses read access to your mailbox only
  for the recipients of mail you've sent and earlier headers in the open thread.

Audit and findings: [docs/SECURITY_QA_REPORT.md](docs/SECURITY_QA_REPORT.md).

## Limitations

- **Low risk is not a guarantee:** a well-made attack from a new, authenticated sender can look clean
  (recall is 63% on the benchmark).
- **Not analyzed:** attachment contents (names and types only), text in images, and domain or URL reputation.
  Request wording is English only.
- **Blind spots:** attack types outside the known sensitive actions (e.g. crypto wallet drainers).
- **Hosting:** quick tunnels change URL on restart. Gmail stops an add-on run after about 30 seconds.

Next steps: domain reputation behind an explicit allow-list, a guarded learned intent classifier validated on
new data, attachment sandboxing, and a hosted backend with managed TLS.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Analysis service unavailable" | The tunnel stopped or changed: `./scripts/start-tunnel.sh`, then `./scripts/push-addon.sh` |
| "Setup needs attention" | The key changed: re-run `./scripts/setup-addon.sh` |
| "Service URL not permitted" | The allow-list doesn't match the current tunnel: `./scripts/push-addon.sh` |
| "Unable to load content" in Gmail | A slow Gmail API call: click **Try again**. Logs: Apps Script editor → **Executions** |
| No MailLens icon | The test deployment isn't installed (Step 5), or Gmail needs a reload |
| Dashboard says the link expired | Links work once and sessions last 8 hours: open it again from Gmail |
| Scan shows "Continue in a Google window" | Your browser blocked Google sign-in inside the page: click it and approve |
| Backend logs | `docker logs maillens` |

## Repository layout

```
addon/      Gmail add-on (Apps Script) and its tests
backend/    FastAPI backend: detection engine, dashboard API, tests, Dockerfile
dashboard/  Security Console (React + Vite), built into the Docker image
demo/ seeder/  Synthetic demo mailbox
scripts/    Setup and run scripts
eval/       Benchmarks (v4 is current), metrics.json, reproduce.py
docs/       Evaluation, security, testing and design documents
```
