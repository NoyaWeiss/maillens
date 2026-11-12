# MailLens

## What is MailLens?

MailLens is a Gmail add-on that tells you whether the email you just opened is safe. It shows a verdict
(**Low risk, Suspicious, High risk or Inconclusive**), the evidence behind it, and what to do next. Analysis
runs on your own machine; no cloud service is involved.

## What it does

- **In Gmail:** a risk card for the open email (verdict, risk index, reasons, recommended action) and a
  detailed analysis on demand.
- **Security Console (dashboard):** your analyzed emails over a 1-hour to 1-year window, search, per-email
  assessments, an optional **Scan Inbox**, benchmark results, and how detection works.
- **Detection approach:** 13 explainable checks.
  - **Is the email lying?** Look-alike domains, a changed Reply-To, links that hide their destination, hidden text.
  - **Is it asking for something risky in a suspicious context?** Bank-detail changes, gift cards, passwords or codes.
  - **How the verdict is reached:** findings are correlated per sender, domain or link and never double-counted. High risk needs strong or corroborated evidence. Missing information never raises the risk.

## Architecture

```
 Gmail ── MailLens add-on (Apps Script) ──HTTPS──► your tunnel ──► backend (Docker, 127.0.0.1:8787)
                                                                    ├─ detection engine (stateless)
                                   "View full dashboard" ─────────► └─ /dashboard/ (React, per-account history)
```
The backend runs **locally** in Docker, bound to 127.0.0.1, and makes no outbound network calls or stores email
bodies. Gmail can only reach public HTTPS, so the add-on reaches it through an **external Cloudflare HTTPS tunnel**
(`cloudflared`, a free quick tunnel that `setup.sh` starts for you; no Cloudflare account needed).

## Quick Start

**You need:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running),
[Node.js 18+](https://nodejs.org/), Python 3.9+, [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
(macOS: `brew install cloudflared`), and a Google account for testing (a dedicated test account is recommended).

```bash
npm install -g @google/clasp
git clone https://github.com/NoyaWeiss/maillens.git && cd maillens
./scripts/setup.sh                 # add --with-demo to also create the synthetic demo mailbox
```

**`setup.sh` does automatically:**
- checks prerequisites
- creates a random API key in `backend/.env` (never printed)
- builds and starts the backend and dashboard in Docker
- starts your HTTPS tunnel
- creates **your own** Apps Script project and uploads the add-on, locked to your tunnel

It is safe to re-run, for example after a tunnel restart. It ends with **"Automated setup complete"** and a link
to your project.

## Google Setup (manual, about 3 minutes)

Google requires these steps from you; `setup.sh` pauses or prints a link for each:

1. **Allow Apps Script access:** turn **Google Apps Script API** to **On** at
   <https://script.google.com/home/usersettings>. If you skip this, `setup.sh` stops and tells you to turn it on.
2. **Log in:** when `setup.sh` asks, a browser opens for `clasp login`. Choose your test account.
3. **Install the add-on:** open the project link `setup.sh` printed, then
   **Deploy → Test deployments → Application(s): Gmail → Install**.
4. **Authorize:** in Gmail, reload the page, open any email and click the **MailLens** icon in the right-hand panel,
   then **Authorize access**. Google shows "Google hasn't verified this app" (expected for your own unpublished
   project): click **Advanced → Go to MailLens → Allow**.

Permissions requested (`addon/appsscript.json`): run in Gmail and read the **open** email; call your backend;
store settings; and `gmail.readonly` for relationship checks and Scan Inbox. You can decline `gmail.readonly`;
MailLens still works, but those two features are unavailable.

> **Not verified on a brand-new account:** these Google steps were tested on the author's own test account,
> not on a fresh reviewer account. If a screen differs, follow Google's prompt.

## Try MailLens

- **Check it's running:** with no email open, the MailLens panel shows **"Analysis service ready"**.
- **Analyze an email:** open any email; its verdict appears in the panel. With `--with-demo` (open the seeder link
  it prints, choose `seedDemoMailbox`, click **Run** once), you get 13 synthetic emails. For example, the newest
  "Re: PO 4471 - office supplies" is **High risk**, "Updated remittance details" is **Suspicious**, and
  "Invoice #1043 from Brightline Studio" is **Low risk**.
- **View detailed analysis:** shows every check and its result.
- **View full dashboard:** opens the Security Console in a new tab. Use the slider to choose a time window,
  search, and click an email for its assessment. **Scan inbox** analyzes up to 50 recent inbox emails; Google
  may ask you to approve once.

## Evaluation

Frozen engine, pre-registered synthetic benchmark of 200 emails (100 malicious, 100 legitimate):

| Precision | Recall | F1 | False-positive rate |
|---|---|---|---|
| 96.9% | 63% | 0.76 | 2% |

The data is synthetic and the categories are small, so real-world performance may differ. Details:
[docs/EVALUATION_REPORT.md](docs/EVALUATION_REPORT.md). Reproduce and run the tests:
```bash
cd backend && uv sync && uv run pytest -q && uv run python ../eval/reproduce.py   # needs uv: https://docs.astral.sh/uv/
cd .. && node --test addon/tests/ dashboard/tests/
```

## Security & Limitations

- **Security:**
  - An API key protects every backend call, and the add-on can only reach your backend host.
  - Every value is escaped, and there is no LLM to prompt-inject.
  - Dashboard links are one-time codes with no credentials in the URL, and accounts are isolated from each other.
- **Privacy:** MailLens analyzes the opened email and, when you allow it, uses read access to your mailbox only
  for the recipients of mail you've sent and earlier headers in the open thread. The dashboard keeps subject,
  sender and verdict (never the body) for up to 1 year; **Clear history** removes it.
- **Limitations:**
  - Low risk is not a guarantee.
  - Attachment contents, text in images and domain reputation are not analyzed.
  - Request detection is English only.
  - Quick-tunnel URLs change on restart.

Details: [docs/SECURITY_QA_REPORT.md](docs/SECURITY_QA_REPORT.md) · [docs/TESTING_PLAN.md](docs/TESTING_PLAN.md) ·
[docs/RELIABILITY.md](docs/RELIABILITY.md).

## Troubleshooting

| Problem | Fix |
|---|---|
| `setup.sh` lists missing prerequisites | Install them from the links shown, then re-run `./scripts/setup.sh` |
| "Docker is installed but not running" | Start Docker Desktop, then re-run |
| Asked to turn on the Apps Script API | Turn it on at script.google.com/home/usersettings, wait about a minute, then re-run |
| "Analysis service unavailable" in Gmail | The tunnel stopped or changed: re-run `./scripts/setup.sh` |
| No MailLens icon in Gmail | Install the test deployment (Google Setup, step 3), then reload Gmail |
| Dashboard says the link expired | Links work once and sessions last 8 hours: open it again from Gmail |
| "Refusing: … belongs to another MailLens checkout" | Another copy or app uses that name or port: run with `MAILLENS_CONTAINER=… MAILLENS_PORT=… MAILLENS_VOLUME=…` |
| Backend logs | `docker logs maillens` |

Want a different HTTPS endpoint? Run `MAILLENS_TUNNEL_URL=https://your-host ./scripts/setup.sh`. Backend only,
with no Google steps: `./scripts/setup.sh --backend-only`.
