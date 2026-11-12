# Stable hosting: Cloud Run vs. a fixed Cloudflare Tunnel

Nothing in this document has been created or enabled. Any option that needs billing or a paid
resource requires the owner's explicit approval first.

## The requirement

The add-on calls the backend over HTTPS from Google's servers. For the demo we need a URL that
does not change, stays up, and does not depend on the presenter's laptop network.

## Comparison

| | Cloud Run | Fixed (named) Cloudflare Tunnel | Current quick tunnel |
|---|---|---|---|
| URL stability | permanent `*.run.app` URL | permanent hostname on your domain | changes on every restart |
| Runs where | Google Cloud | your laptop | your laptop |
| Depends on laptop and network at demo time | no | yes | yes |
| Accounts needed | Google Cloud project with a **billing account attached** (needed even for free-tier use) | Cloudflare account plus **a domain on Cloudflare** | none |
| Expected cost for this prototype | typically $0 within the free tier; keeping one instance always warm on demo day costs a small daily amount (check the current pricing page) | free plan; a domain costs money if you don't own one | free |
| Cold start | yes (roughly seconds) unless a minimum instance is kept | none | none |
| Secret handling | API key via Secret Manager or an environment variable | stays in local `.env` | stays in local `.env` |
| Matches spec section 6 | yes (the spec's plan) | partially (it was the spec's fallback) | fallback only; Cloudflare positions quick tunnels for testing |
| Setup effort | install gcloud, log in, create project, deploy a container (scriptable) | install a cert, create the tunnel, add a DNS route (scriptable) | already scripted |

## Recommendation

**Cloud Run as primary, quick tunnel as fallback.**
- Cloud Run removes the two biggest demo-day risks: a changing URL, and dependence on the venue's network.
- The quick tunnel is already scripted (`scripts/dev.sh` then `scripts/push-addon.sh`) and makes
  a good offline fallback.
- A named Cloudflare tunnel only makes sense if you already own a domain on Cloudflare. It
  still depends on your laptop and its network.

## What Cloud Run needs from you (when approved)

1. A Google Cloud project with billing attached. You approve the billing; I don't create it.
2. A `gcloud auth login` in the terminal (your interactive login).
3. Then I can script: building the image, deploying with the API key from Secret Manager, a
   production mode with dev-only logging off, and updating the add-on's backend URL.

---

## Phase 3 addendum (2026-11-12): Cloud Run plan, costs, and closing F-09

The owner prefers Cloud Run. **Nothing has been created; billing is not enabled.**

### Setup steps (all reversible; the owner approves step 1)

1. **Owner:** create or select a Google Cloud project and attach a billing account. Set a **budget alert**
   (e.g. $5/month) at the same time.
2. **Owner:** run `gcloud auth login` in the terminal (an interactive Google login).
3. **Scripted (by me, after approval):**
   - enable the Cloud Run, Artifact Registry and Secret Manager APIs
   - create a dedicated service account with **no** IAM roles
   - store the API key in Secret Manager
   - build the container locally (Docker is installed) and push it
   - deploy:
     ```
     gcloud run deploy maillens --image … --region <region> \
       --service-account maillens-run@… --set-secrets MAILLENS_API_KEY=maillens-api-key:latest \
       --set-env-vars MAILLENS_ENV=prod --cpu 1 --memory 512Mi \
       --concurrency 20 --max-instances 2 --min-instances 0 --allow-unauthenticated
     ```
   - update the add-on's backend URL and push the production build

### Why `--allow-unauthenticated` with an API key (and not Cloud Run IAM)

The add-on calls the backend from Apps Script. Cloud Run IAM would need a Google-signed ID token whose
audience is the service URL, and Apps Script's `ScriptApp.getIdentityToken()` can't set that audience.
So the service accepts traffic at the network level and enforces the **application-level API key**
(constant-time comparison, rate limited before authentication). Requests without the key get 401
(verified on the tunnel today).

### Estimated cost (estimates; check the current Cloud Run pricing page before approving)

| Item | Expected usage | Estimate |
|---|---|---|
| Requests and CPU at demo scale (hundreds of ~50 ms requests) | far below the monthly free tier (2 M requests, 180k vCPU-seconds, 360k GiB-seconds) | **≈ $0** |
| `--min-instances 1` to avoid a cold start during the demo | 1 small instance idle for one day | roughly **$0.20–$0.50 per day**; turn it off afterwards (left on: several dollars per month) |
| Artifact Registry (one ~150 MB image) | free tier 0.5 GB | ≈ $0 |
| Secret Manager (1 secret) | free tier covers a few active versions | ≈ $0 |

Cost controls: `--max-instances 2`, a budget alert, and minimum instances only on demo day.

### How Cloud Run closes F-09

F-09: the manifest has no `urlFetchWhitelist`, so the add-on could send requests, including the API
key, to any HTTPS URL typed into Advanced settings. With a stable `https://maillens-…run.app` URL, the
manifest can allow exactly:
- `https://<service>.run.app/` (the backend)
- `https://gmail.googleapis.com/` (relationship lookups)

Apps Script then refuses any other destination. This needs one live check after deployment: confirm the
allow-list is enforced for a **test deployment**, because Google documents it as required for
*published* add-ons.

### Options that don't need a paid deployment

| Option | Closes F-09? | Notes |
|---|---|---|
| **A. Remove the editable service URL** from Advanced settings; the URL comes only from the deployment config (`Secrets.js` or script properties) | **Mostly:** removes the "type any URL" path, the main way the key could be sent elsewhere | A small UI change to an unapproved screen, so it needs the owner's OK; no cost |
| B. `urlFetchWhitelist` with `https://*.trycloudflare.com/` | Partially: anyone can create a trycloudflare host | Wildcard support and test-deployment enforcement must be verified live |
| C. Named Cloudflare tunnel on a domain you own | Yes (stable hostname allow-list) | Free Cloudflare plan, but needs a domain (paid if you don't own one) and still depends on the laptop |

**Recommendation:** do **A** now (no cost, removes the main risk). Add the exact `urlFetchWhitelist` once a
stable hostname exists (Cloud Run, or C).
