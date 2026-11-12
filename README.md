# MailLens: See Beyond the Inbox

MailLens is a Gmail add-on that analyzes the open email and answers one question: **what does this
email claim, and what is actually true?** It shows a verdict (Low, Suspicious, High or Inconclusive), a
risk index, the evidence behind it, and what to do next.

It flags an email for one of two reasons, and labels which one applied:
- **it lies:** observed contradictions such as a Reply-To that changed mid-thread, a look-alike domain,
  link text that hides its real destination, or hidden text aimed at scanners
- **it asks for something irreversible in an unusual context:** bank-detail changes, gift cards,
  verification codes, payroll changes

**Design principle: a High verdict needs corroboration.** No single weak signal can produce High, every
signal has a tested false-positive guard, and "unknown" never escalates.

> Built for the Upwind Security Analyst home assignment. Everything here runs on your own machine,
> with your own Google account. No cloud service or third-party API is required.

---

## Contents
1. [Architecture](#1-architecture)
2. [Run it yourself (reviewer setup)](#2-run-it-yourself-reviewer-setup)
3. [Demo walkthrough](#3-demo-walkthrough)
4. [How detection works](#4-how-detection-works)
5. [Security and privacy](#5-security-and-privacy)
6. [Testing](#6-testing)
7. [Troubleshooting](#7-troubleshooting)
8. [Limitations and trade-offs](#8-limitations-and-trade-offs)
9. [Repository layout and further docs](#9-repository-layout-and-further-docs)

---

## 1. Architecture

```
 Gmail (your account)
   │  opens an email
   ▼
 Gmail add-on (Google Apps Script, addon/)                 Backend (FastAPI, backend/)
   - reads headers, body and attachment metadata    HTTPS  - parses untrusted input (strict limits)
     of the OPEN email only (current-message token) ──────►- 13 detection signals + guards
   - thread digest: earlier messages' headers        API   - entity deduplication, decision gates
   - optional relationship facts from Sent-mail      key   - template-based explanations (no LLM)
     headers (gmail.readonly, opt-in)               ◄──────- stateless: no database, no outbound calls
   - renders the cards (CardService)                verdict
```

- **Split of responsibilities:** the add-on extracts and renders. All analysis lives in the backend,
  where it is unit-tested.
- **Connectivity:** the backend runs on your machine (Docker). Gmail reaches it through **your own**
  HTTPS tunnel (a free Cloudflare quick tunnel).
- **Sent to the backend:** From, Reply-To, Subject, all Authentication-Results headers, a bulk flag,
  the body (capped), attachment names and types (never their bytes), a digest of up to 5 earlier thread
  messages (headers only), and relationship facts (counts and matched addresses; never contact names).

## 2. Run it yourself (reviewer setup)

About 20–30 minutes on a fresh machine. Steps marked 👤 need your own Google login or a click in a
Google page; everything else is scripted.

### Prerequisites
- **Docker** (Docker Desktop on macOS or Windows)
- **Python 3.9+** (only for small helper scripts)
- **Node.js 18+** and **clasp**: `npm install -g @google/clasp`
- **cloudflared**: <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/>
- A **Google account for testing.** A dedicated test account is recommended, because the add-on can request read access to the mailbox.

### Step 1: Start the backend (Docker)
```bash
git clone <this-repo> maillens && cd maillens
./scripts/run-backend-docker.sh
```
This creates `backend/.env` with **your own random API key** (gitignored, mode 600), builds the image,
and runs it bound to `127.0.0.1:8787` in production mode. Expected output ends with
`{"status":"ok"}  <- backend is up`.

### Step 2: Expose it over HTTPS with your own tunnel
```bash
./scripts/start-tunnel.sh
```
This prints `https://<random>.trycloudflare.com` once it is publicly reachable; a new hostname can take
1–2 minutes. Quick-tunnel URLs change on every restart, so re-run Step 4 afterwards.

### Step 3: 👤 Allow Apps Script access and log clasp in
1. Open <https://script.google.com/home/usersettings> and set **Google Apps Script API** to **On**.
2. Run `clasp login` and choose your test account.

### Step 4: Create and push your add-on
```bash
./scripts/setup-addon.sh            # uses the tunnel URL from Step 2
```
This does three things:
- creates **your** Apps Script project (first run only)
- generates the gitignored `addon/Secrets.js` with your backend URL and API key
- injects the manifest allow-list `urlFetchWhitelist` = **exactly** your backend host plus the Gmail
  API, then pushes the production build

### Step 5: 👤 Install and authorize the add-on
1. Open the editor link the script printed, then **Deploy → Test deployments → Gmail → Install**.
2. Open Gmail, open any email, click the **MailLens** icon in the right-hand side panel, then
   **Authorize access**. Google warns "Google hasn't verified this app"; this is expected for your own
   unpublished script. Choose **Advanced → Go to MailLens**, then **Select all** and **Continue**.

The permissions:
- **Required:** run as a Gmail add-on; read the **open** message; connect to an external service
  (your backend); store add-on data.
- **Optional:** "View your email messages and settings" (`gmail.readonly`) for relationship checks.
  If you decline it, MailLens still works, and the relationship checks show as unavailable.

### Step 6: Seed the synthetic demo mailbox (optional, recommended)
```bash
./scripts/setup-seeder.sh
```
👤 Then open the printed link, choose **`seedDemoMailbox`**, click **Run** once, and authorize (its
only Gmail permission is **insert**: it can add messages but can't read anything). This adds 13 synthetic
emails (`.example` domains) to your inbox and Sent folder.

### Step 7: Verify
- With no email open, click MailLens: **"Analysis service ready"** appears.
- Open "Re: PO 4471 - office supplies" (the newest message): **High risk**.

## 3. Demo walkthrough

| Email (seeded) | What it tests | Expected |
|---|---|---|
| T1 "Invoice #1043 from Brightline Studio" | Billing platform; link off the From domain but on its signing domain | Low |
| T2 "New sign-in to your CloudMail account" | Real security alert that asks you to sign in | Low, with advice |
| T3 "Last chance: early-bird tickets…" | Newsletter: hidden preheader, tracked links, urgency | Low |
| T4 backup "Quick favor" | Known contact's name from a new address, plus an availability probe | High |
| T5 newest "Re: PO 4471…" | Reply-To added mid-thread, plus a bank-detail change | High |
| T6 "Updated remittance details" | Bank change from a known vendor, nothing else wrong | Suspicious (verify by phone) |
| T7 "Remittance advice INV-2207" | Look-alike vendor domain `acmesupp1y`, plus an HTML attachment | High |
| T8 "Action required: verify your account" | Hidden text aimed at scanners, deceptive link, brand mismatch | High |
| T9 "Fwd: Your mailbox is almost full" | No authentication results, plus a credential request | Inconclusive |

Suggested 7-minute script:
1. T1 vs. T4: both are urgent, with opposite verdicts.
2. T6 vs. T5: the same request gets a different verdict because of one observed contradiction.
3. T7.
4. T9, then **View detailed analysis** to show coverage and uncertainty.
5. The test suites.

> The seeded emails carry **simulated** Authentication-Results headers: Gmail's insert API performs no
> SPF/DKIM checks. For a live check, send T4-style mail from a second real account.

## 4. How detection works

- **Signals (S1–S14):**

  | Area | Signals |
  |---|---|
  | Authentication | Google's topmost result only |
  | Reply-To | divergence, including a change mid-thread |
  | Sender identity | display-name deception, known-contact name collision, look-alike domains (including homoglyphs and mixed scripts), sender familiarity |
  | Thread | thread anomalies |
  | Links | link-text deception, deceptive URL construction (including OAuth consent links requesting mail access) |
  | Content | risky attachments (metadata only), hidden or disguised content, high-impact requests, pressure and secrecy |

- **Evidence model:** findings are keyed by **entity**, so one bad domain counts once, not as identity,
  authentication and link findings together.
- **Decision gates:**

  | Verdict | Rule |
  |---|---|
  | **High** | H-A: a deliberate construct (homoglyph domain, `user@host` link trick, disguised executable, hidden text aimed at scanners); or H-B: a strong finding plus a risky request, or strong findings on two entities; or H-C: an irreversible request plus two corroborators |
  | **Suspicious** | one strong finding, an irreversible request alone ("verify out-of-band"), or a narrow pretext pattern (an unexplained favor plus secrecy from an unfamiliar sender) |
  | **Inconclusive** | exactly one rule: the sender can't be authenticated, and there's a risky request or anomaly |

- **The risk index** is a position within the verdict's band, **not a probability**.
- **Explanations** come from fixed templates. Observed facts and inferences are kept separate;
  categories are hedged ("Possible …"); quotes come from one labelled source with links defanged.

Full specification and rationale: `docs/` (see section 9).

## 5. Security and privacy

| Area | Control |
|---|---|
| Untrusted input | Strict schemas with size limits on every field; 1 MB request cap; bounded HTML parser (depth- and size-limited); regex patterns tested against catastrophic backtracking |
| Prompt injection | No LLM. Hidden text aimed at scanners is itself a high-severity finding; tests prove injected text never lowers a verdict |
| Backend exposure | API key on every analysis or status call (constant-time comparison); rate limit before authentication; no docs or OpenAPI endpoint; no stack traces; **no outbound network calls** (enforced in tests) |
| Add-on outbound calls | Manifest `urlFetchWhitelist` = exactly your backend host plus the Gmail API, enforced by Google; the deployment config can't be overridden by a saved setting |
| Rendering | Every value HTML-escaped; label data stripped of markup; URLs defanged and never clickable |
| Secrets | `backend/.env` and the generated `addon/Secrets.js` and `.clasp.json` are gitignored; the API key is never shown in the UI |
| Logs | Request ID, verdict, gate, signal IDs and timing only; never email content (tested) |
| OAuth scopes | 5 scopes. `gmail.readonly` is optional, used only for Sent-mail headers and earlier thread headers; `gmail.metadata` was rejected on evidence, because it makes the open email's body unreadable |

Details and findings: `docs/SECURITY_QA_REPORT.md`.

## 6. Testing

```bash
cd backend && uv sync && uv run pytest -q     # without uv: pip install -r requirements.txt && pip install pytest httpx && pytest -q
node --test addon/tests/                      # add-on: card rendering, escaping, failure paths
node addon/tests/contract.mjs http://127.0.0.1:8787 "$(grep MAILLENS_API_KEY backend/.env | cut -d= -f2-)"
```

| Suite | Count | What it covers |
|---|---|---|
| Backend | 226 tests | per-signal must-fire / must-not-fire; engine invariants (exhaustive grid); the demo scenarios; adversarial input; grounding of explanations; a decision snapshot proving presentation changes never alter verdicts |
| Add-on | 73 tests | every card rendered for real backend responses through a strict CardService double (Gmail's render-time rules), hostile-string escaping, failure paths |
| Development cases | 41 pre-registered, labelled (`backend/tests/phase3/`) | Ground truth committed before the first run. Baseline: 11/20 malicious detected, 3 false positives. After narrow fixes: 16/20 detected, 1 false positive. **Development tests, not a benchmark;** see `docs/TESTING_PLAN.md` |

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Analysis service unavailable" | Tunnel URL changed or the tunnel stopped. Run `./scripts/start-tunnel.sh`, then `./scripts/setup-addon.sh`. The grey **Details** line names the host and the error |
| "Setup needs attention" | The backend rejected the key: re-run `./scripts/setup-addon.sh` after any change to `backend/.env` |
| "Service URL not permitted" | The add-on's allow-list doesn't contain the current backend host: re-run `./scripts/setup-addon.sh` |
| "Unable to load content" in Gmail | Usually a Gmail API stall past Gmail's 30 s limit: click **Try again**. Execution logs: Apps Script editor → **Executions** |
| No MailLens icon | The test deployment isn't installed (Step 5), or Gmail needs a reload |
| `clasp create-script` changed `addon/appsscript.json` | `setup-addon.sh` restores it; otherwise run `git checkout addon/appsscript.json` |
| Backend logs | `docker logs maillens` |

## 8. Limitations and trade-offs

- **Blind spots:** a first-contact plain-text phish from attacker-owned infrastructure with valid
  authentication; instructions only inside images (no OCR); no threat-intelligence or URL reputation;
  English-only request patterns; a compromised known contact sending a link-based phish can rate Low.
- **Known false positive:** a colleague forwarding a phish to IT is rated High (forwarded content is
  evaluated as the forwarder's own).
- **Hosting:** quick tunnels have no uptime guarantee and change URL on restart. Gmail stops an add-on
  run at ~30 s, and a rare Gmail API stall (32 s observed once) can exceed it.
- **Permissions:** relationship checks need `gmail.readonly`, which is broad. The code reads only
  Sent-mail headers and the open email.
- **Ordinal rules over fitted weights:** there's no labelled data, so numeric precision would be invented.

## 9. Repository layout and further docs

```
addon/      Gmail add-on (Apps Script): extraction, cards, tests (node --test)
backend/    FastAPI service: signals, decision engine, presentation, tests (pytest), Dockerfile
demo/       Synthetic demo-mailbox generator (build_seed.py)
seeder/     Apps Script project that inserts the demo emails (gmail.insert only)
scripts/    run-backend-docker, start-tunnel, setup-addon, setup-seeder, push-addon, gas_api helper
docs/       Design and verification documents
```

| Document | Contents |
|---|---|
| `docs/SECURITY_QA_REPORT.md` | Phase 3 audit: findings, fixes, PASS / FAIL / NOT VERIFIED |
| `docs/TESTING_PLAN.md` | Development testing vs. independent evaluation, evaluation policy |
| `docs/RELIABILITY.md` | Measured latency in real Gmail, stall analysis |
| `docs/UI_PROPOSAL.md` | Card design decisions and CardService constraints |
| `docs/ROADMAP.md` | Phases and their status |
| `docs/HOSTING.md` | Hosting notes (local + tunnel is the supported setup; cloud is optional and not required) |
