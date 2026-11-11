"""Domain utilities: registrable domains (offline PSL), reference lists, confusables.

Every comparison between domains goes through `normalize_domain` first
(IDNA decode, NFKC, casefold) so that visually identical inputs compare equal.
"""

import unicodedata
from functools import lru_cache

from publicsuffixlist import PublicSuffixList

# Bundled snapshot shipped inside the package; never downloaded at runtime.
_PSL = PublicSuffixList()

FREEMAIL = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "ymail.com", "outlook.com", "hotmail.com",
    "live.com", "msn.com", "aol.com", "icloud.com", "me.com", "mac.com", "proton.me", "protonmail.com",
    "gmx.com", "gmx.net", "mail.com", "yandex.com", "yandex.ru", "zoho.com", "tutanota.com", "fastmail.com",
})

SHORTENERS = frozenset({
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "rebrand.ly", "cutt.ly",
    "t.ly", "rb.gy", "shorturl.at", "tiny.cc", "s.id",
})

# Email service providers / click trackers whose redirect links are normal in legitimate mail.
ESP_TRACKERS = frozenset({
    "sendgrid.net", "list-manage.com", "mailchimp.com", "mcusercontent.com", "hubspotlinks.com",
    "hs-sites.com", "mandrillapp.com", "sparkpostmail.com", "mailgun.org", "constantcontact.com",
    "rs6.net", "exacttarget.com", "salesforce.com", "klaviyo.com", "customer.io", "substack.com",
})

# Small, deliberately conservative brand list: display-name token -> domains the brand owns.
# The two .example brands exist only so the synthetic demo mailbox can exercise the check.
BRANDS: dict[str, frozenset[str]] = {
    "paypal": frozenset({"paypal.com"}),
    "microsoft": frozenset({"microsoft.com", "office.com", "live.com", "outlook.com", "microsoftonline.com"}),
    "office 365": frozenset({"microsoft.com", "office.com", "office365.com"}),
    "google": frozenset({"google.com", "gmail.com", "youtube.com"}),
    "apple": frozenset({"apple.com", "icloud.com"}),
    "amazon": frozenset({"amazon.com", "amazon.co.uk", "amazon.de", "amazonses.com"}),
    "docusign": frozenset({"docusign.com", "docusign.net"}),
    "dropbox": frozenset({"dropbox.com", "dropboxmail.com"}),
    "netflix": frozenset({"netflix.com"}),
    "dhl": frozenset({"dhl.com", "dhl.de"}),
    "fedex": frozenset({"fedex.com"}),
    "linkedin": frozenset({"linkedin.com"}),
    "facebook": frozenset({"facebook.com", "facebookmail.com", "meta.com"}),
    "northwind bank": frozenset({"northwindbank.example"}),
    "cloudmail": frozenset({"cloudmail.example"}),
}

# Common visual confusables mapped to a Latin skeleton. Deliberately excludes i<->l,
# which would make e.g. "mail" and "mall" collide (a false-positive source).
_CONFUSABLES = {
    "0": "o", "1": "l", "3": "e", "5": "s", "$": "s", "@": "a",
    # Cyrillic
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "ԁ": "d", "ӏ": "l", "һ": "h", "ԛ": "q", "ԝ": "w",
    # Greek
    "α": "a", "ο": "o", "ρ": "p", "ν": "v", "τ": "t", "ι": "i", "κ": "k",
}
_MULTI = (("rn", "m"), ("vv", "w"), ("cl", "d"))


def normalize_domain(domain: str) -> str:
    d = (domain or "").strip().strip(".").lower()[:253]
    if "xn--" in d:
        try:
            d = d.encode("ascii").decode("idna")
        except UnicodeError:
            pass
    return unicodedata.normalize("NFKC", d).casefold()


@lru_cache(maxsize=4096)
def registrable(domain: str) -> str:
    """eTLD+1 using the offline PSL; falls back to the input for unknown/invalid names."""
    d = normalize_domain(domain)
    if not d:
        return ""
    return _PSL.privatesuffix(d) or d


def base_label(reg_domain: str) -> str:
    """'acmesupply.example' -> 'acmesupply' (strip the public suffix)."""
    suffix = _PSL.publicsuffix(reg_domain) or ""
    if suffix and reg_domain.endswith("." + suffix):
        return reg_domain[: -len(suffix) - 1]
    return reg_domain.split(".", 1)[0]


def skeleton(label: str) -> str:
    s = "".join(_CONFUSABLES.get(ch, ch) for ch in unicodedata.normalize("NFKC", label).casefold())
    for a, b in _MULTI:
        s = s.replace(a, b)
    return s


def scripts_in(label: str) -> set[str]:
    out = set()
    for ch in label:
        if ch.isalpha():
            name = unicodedata.name(ch, "")
            out.add(name.split(" ", 1)[0] if name else "UNKNOWN")
    return out


def is_mixed_script(label: str) -> bool:
    return len(scripts_in(label)) > 1


def edit_distance(a: str, b: str, cap: int = 3) -> int:
    """Levenshtein distance, short-circuiting once it exceeds `cap`."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def is_freemail(domain: str) -> bool:
    return registrable(domain) in FREEMAIL


def defang(text: str) -> str:
    """Make URLs/domains non-clickable for display: https://a.b -> hxxps://a[.]b"""
    return text.replace("http", "hxxp").replace(".", "[.]")
