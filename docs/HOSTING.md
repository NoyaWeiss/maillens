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
