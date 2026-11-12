#!/usr/bin/env bash
# Installs the command-line tools MailLens needs into the project's own .tools/ folder, only if they are
# missing: Node.js (for clasp), clasp (Google Apps Script CLI) and cloudflared (HTTPS tunnel).
# No sudo, no Homebrew, no global npm installs. Official builds, pinned versions, checksums verified.
#   scripts/install-tools.sh node clasp cloudflared     (asks before each download; MAILLENS_YES=1 to skip asking)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/.tools"; BIN="$TOOLS/bin"
mkdir -p "$BIN"; export PATH="$BIN:$PATH"
NODE_VERSION=20.18.0          # Node.js LTS
CLASP_VERSION=3.4.1           # @google/clasp
CF_VERSION=2026.10.3          # cloudflared; SHA-256 of the binary as published in Cloudflare's release notes
CF_SHA_darwin_arm64=f249139e0541fa589c987397d867cc16c83ab1236d31eb6782f2e4552ee9cf80
CF_SHA_darwin_amd64=947e2942d6a59922d80190d23b12f3ade8da16e23e3bd937182a48993b7c00db
CF_SHA_linux_amd64=053b80b0a23031a038fdbf3c073f59f82b8f1f152aa67971d7383ffafc0dbab0
CF_SHA_linux_arm64=89297ebfb9e8c99c0dc013a1140601453cf3798d8306c5591651f4a3f5210be8

die() { printf "\033[31m✗ %s\033[0m\n" "$1"; exit 1; }
ok() { printf "\033[32m✓\033[0m %s\n" "$1"; }
sha256() { if command -v shasum >/dev/null; then shasum -a 256 "$1" | cut -d' ' -f1; else sha256sum "$1" | cut -d' ' -f1; fi; }
ask() {  # consent before any download
  [ "${MAILLENS_YES:-}" = "1" ] && return 0
  read -r -p "   $1 [Y/n] " a || return 1
  case "$a" in ""|y|Y|yes) return 0;; *) return 1;; esac
}
case "$(uname -s)" in Darwin) OS=darwin;; Linux) OS=linux;; *) die "Unsupported OS $(uname -s). On Windows, run MailLens inside WSL2 (Ubuntu).";; esac
case "$(uname -m)" in arm64|aarch64) ARCH=arm64;; x86_64|amd64) ARCH=x64;; *) die "Unsupported CPU $(uname -m)";; esac
TMP="$(mktemp -d)"

node_ok() { command -v node >/dev/null && [ "$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)" -ge 18 ]; }
install_node() {
  node_ok && { ok "Node.js $(node -v) found"; return; }
  ask "Node.js 18+ is missing. Download Node.js $NODE_VERSION (official build, ~45 MB) into .tools/?" || die "Node.js is required for clasp. Install it from https://nodejs.org/ and re-run."
  local f="node-v$NODE_VERSION-$OS-$ARCH.tar.gz"
  curl -fsSL -o "$TMP/$f" "https://nodejs.org/dist/v$NODE_VERSION/$f" || die "download failed: https://nodejs.org/dist/v$NODE_VERSION/$f"
  curl -fsSL -o "$TMP/SHASUMS256.txt" "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt" || die "could not fetch Node.js checksums"
  [ "$(sha256 "$TMP/$f")" = "$(grep " $f\$" "$TMP/SHASUMS256.txt" | cut -d' ' -f1)" ] || die "Node.js checksum mismatch; nothing was installed"
  mkdir -p "$TOOLS/node" && tar -xzf "$TMP/$f" -C "$TOOLS/node" --strip-components 1 || die "could not unpack Node.js"
  for t in node npm npx; do ln -sf "$TOOLS/node/bin/$t" "$BIN/$t"; done
  node_ok && ok "Node.js $(node -v) installed in .tools/ (checksum verified)" || die "Node.js did not start"
}
install_clasp() {
  command -v clasp >/dev/null && { ok "clasp found"; return; }
  install_node
  ask "clasp (Google Apps Script CLI) is missing. Install @google/clasp@$CLASP_VERSION into .tools/ (no sudo)?" || die "clasp is required. Install it with: npm install -g @google/clasp"
  npm install --prefix "$TOOLS/clasp" --no-audit --no-fund --loglevel=error "@google/clasp@$CLASP_VERSION" >/dev/null || die "npm could not install clasp (network?). Re-run to retry."
  ln -sf "$TOOLS/clasp/node_modules/.bin/clasp" "$BIN/clasp"
  clasp --version >/dev/null 2>&1 && ok "clasp $(clasp --version | head -1) installed in .tools/" || die "clasp did not start"
}
install_cloudflared() {
  command -v cloudflared >/dev/null && { ok "cloudflared found"; return; }
  ask "cloudflared (Cloudflare tunnel) is missing. Download cloudflared $CF_VERSION (official build, ~40 MB) into .tools/?" || die "cloudflared is required unless you set MAILLENS_TUNNEL_URL. Download: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
  local a="${ARCH/x64/amd64}" url sha_var
  sha_var="CF_SHA_${OS}_${a}"
  if [ "$OS" = darwin ]; then
    url="https://github.com/cloudflare/cloudflared/releases/download/$CF_VERSION/cloudflared-darwin-$a.tgz"
    curl -fsSL -o "$TMP/cf.tgz" "$url" || die "download failed: $url"
    tar -xzf "$TMP/cf.tgz" -C "$TMP" || die "could not unpack cloudflared"
  else
    url="https://github.com/cloudflare/cloudflared/releases/download/$CF_VERSION/cloudflared-linux-$a"
    curl -fsSL -o "$TMP/cloudflared" "$url" || die "download failed: $url"
  fi
  [ "$(sha256 "$TMP/cloudflared")" = "${!sha_var}" ] || die "cloudflared checksum mismatch; nothing was installed"
  install -m 755 "$TMP/cloudflared" "$BIN/cloudflared"
  cloudflared --version >/dev/null 2>&1 && ok "cloudflared $CF_VERSION installed in .tools/ (checksum verified)" || die "cloudflared did not start"
}
for t in "$@"; do "install_$t"; done
