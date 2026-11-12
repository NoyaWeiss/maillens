"""Phase 5b v2 HOLDOUT generator (seed 5512). Written AFTER the engine freeze (eval/v2/FREEZE.md) and
before any v2 run. New organization, people, vendors and scenario types; no v1 scenario is reused or
paraphrased. Only neutral email-building helpers (headers, greetings/closings, near-duplicate guard) are
shared with v1. Labels come from each scenario's intent, never from MailLens output.
"""

import importlib.util
import json
import random
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location("v1gen", Path(__file__).resolve().parents[1] / "v1" / "generate.py")
v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v1)  # helpers only: auth, payload, html, add-with-dedup

R = random.Random(5512)
v1.RNG = R
v1.CASES.clear()
v1._TOKENS.clear()
OUT = Path(__file__).with_name("dataset.jsonl")
auth, payload, html, add = v1.auth, v1.payload, v1.html, v1.add

ORG = "lattice-dynamics.example"
PEOPLE = [("Ella Brandt", "ella.brandt"), ("Jonah Weiss", "jonah.weiss"), ("Priya Nair", "priya.nair"),
          ("Mateo Ruiz", "mateo.ruiz"), ("Hannah Ito", "hannah.ito"), ("Sam Okafor", "sam.okafor")]
CEO, CFO = ("Irene Volkov", "irene.volkov"), ("Marcus Hale", "marcus.hale")
VENDORS = [("Copperline Freight", "copperline-freight.example", "payables"),
           ("Nimbus Office Supply", "nimbusofficesupply.example", "orders"),
           ("Arbor Legal", "arborlegal.example", "closings"),
           ("Quillstone Analytics", "quillstone.example", "finance")]
PARTNERS = [("Ravi Menon", "ravi.menon", "quillstone.example"), ("Lena Fischer", "lena.fischer", "arborlegal.example"),
            ("Tomas Berg", "tomas.berg", "copperline-freight.example")]
KNOWN = [ORG] + [v[1] for v in VENDORS] + ["benefitsflow.example"]
FREE = ["gmail.com", "outlook.com", "yahoo.com", "proton.me", "aol.com"]


def rel(sent=0, names=()):
    return {"window_days": 180, "known_domains": KNOWN, "sender_sent_count": sent, "name_match_addresses": list(names)}


def p(seq):
    return R.choice(seq)


def amt():
    return f"${R.randint(12, 480) * 1000:,}"


def ref():
    return f"{p(['FILE', 'ESC', 'MATTER', 'CASE'])}-{R.randint(10000, 99999)}"


# ================================================================== MALICIOUS (100)
def m_escrow(n):
    t = ["Ahead of tomorrow's closing on {r}, please note our trust account has changed. Wire the {a} balance using the attached instructions.",
         "Our escrow bank is under review, so funds for {r} must go to the alternate account below. Please confirm once sent.",
         "Final wiring instructions for {r} are attached. Disregard any previous instructions; time is of the essence.",
         "Please update the beneficiary for the {r} settlement to the account in this email before end of day."]
    for i in range(n):
        name, local, dom = PARTNERS[1]
        k = i % 3
        if k == 0:
            frm, a, rt, ctx = f"{name} <{local}@arb0rlegal.example>", auth("arb0rlegal.example"), None, "look-alike of the known law firm"
        elif k == 1:
            frm, a, rt, ctx = f"{name} <{local}@{dom}>", auth(dom), f"{name} <{local}.esq@{p(FREE)}>", "real firm address, free-mail Reply-To"
        else:
            frm, a, rt, ctx = f"Arbor Legal Closings <closings@arborlegal-escrow.example>", auth("arborlegal-escrow.example"), None, "law-firm name plus 'escrow'"
        add("Malicious", "real-estate / escrow wire fraud", "VM1", "medium", "Attacker redirects closing funds to their own account.", ctx,
            payload(frm, p(["Closing funds", f"Wiring instructions {ref()}", "Settlement update"]), html(t[i % 4].format(r=ref(), a=amt())),
                    auth_results=a, reply_to=rt, relationship=rel(sent=3 if k == 1 else 0),
                    attachments=[("Wire_Instructions.pdf", "application/pdf", 61000)] if i % 2 else ()))


def m_invoice_portal(n):
    for i in range(n):
        dom = p(["nimbus-invoicehub.example", "paydesk-copperline.example", "ap-portal-center.example", "invoice-review.example"])
        img = i % 3 == 0
        body = ("Scan the code in the attached image to view and pay your invoice." if img else
                p(["Your invoice is ready. Pay it securely through our new portal.", "An invoice is overdue. Review and settle it via the portal to avoid fees."]))
        links = () if img else [(p(["Pay invoice", "Open portal", "View statement"]), f"https://{dom}/inv/{R.randint(1000, 9999)}")]
        add("Malicious", "fake invoice portal / QR", "VM2", "hard" if img else "medium", "Fake invoice portal collecting payments or credentials.",
            "unfamiliar sender" + ("; instruction in an image (QR)" if img else ""),
            payload(f"{p(['Accounts Receivable', 'Billing Desk', 'Nimbus Billing'])} <billing@{dom}>", p(["Invoice ready", "Overdue invoice", "Statement"]),
                    html(body, links=links), auth_results=auth(dom), relationship=rel(),
                    attachments=[("invoice_qr.png", "image/png", 88000)] if img else ()))


def m_notification_lure(n):
    lures = [("RingCentral", "New fax received (3 pages)", "You have a new fax. Sign in to view the document."),
             ("Microsoft Teams", "You have 3 unread messages", "Your colleagues are trying to reach you. Sign in to read your messages."),
             ("Zoom", "Missed meeting recording", "A recording was shared with you. Log in with your work account to watch it."),
             ("Voicemail Service", "Voicemail from +1 (415) ***-**27", "Listen to your voicemail. Sign in to verify your identity first."),
             ("Adobe", "Document shared via Adobe", "A PDF was shared with you. Sign in with your email password to open it.")]
    for i in range(n):
        brand, subj, body = lures[i % 5]
        dom = f"{brand.split()[0].lower()}-{p(['notify', 'messages', 'share', 'center'])}{p(['.example', '-mail.example'])}"
        add("Malicious", "notification lure (fax / voicemail / chat)", "VM3", "medium", f"Fake {brand} notification leading to a credential page.",
            "unfamiliar sender; brand-style display name",
            payload(f"{brand} <no-reply@{dom}>", subj, html(body, links=[(p(["Open", "View", "Listen", "Sign in"]), f"https://{dom}/v/{R.randint(100, 999)}")]),
                    auth_results=auth(dom), relationship=rel()))


def m_hr_policy(n):
    for i in range(n):
        dom = p(["lattice-dynamics-hr.example", "latticedynamics-people.example", "lattice-hr-portal.example"])
        body = p(["Please review and sign the updated employee handbook by Friday. Sign in with your company credentials.",
                  "All staff must acknowledge the new remote-work policy. Log in to confirm your acknowledgement.",
                  "Your 2026 salary adjustment letter is ready. Sign in to view it."])
        add("Malicious", "HR / policy acknowledgement phish", "VM4", "medium", "Fake HR portal impersonating the company to harvest credentials.",
            "imitation of the company's own domain",
            payload(f"{p(['People Team', 'HR Department', 'Human Resources'])} <hr@{dom}>", p(["Action required: policy", "Handbook acknowledgement", "Salary letter"]),
                    html(body, links=[("Open portal", f"https://{dom}/ack")]), auth_results=auth(dom), relationship=rel()))


def m_cfo_wire(n):
    for i in range(n):
        name, local = CFO
        free = i % 2 == 0
        frm = f"{name} <{local}.cfo@{p(FREE)}>" if free else f"{name} <{local}@{ORG}>"
        a = auth("gmail.com") if free else auth(ORG, dmarc="fail", spf="fail", dkim="none")
        body = p(["I need a wire of {a} sent today for a confidential deal. Please keep this between us until we announce.",
                  "Process a same-day transfer of {a} to the account I'll send next. Don't loop in anyone else.",
                  "Can you handle an urgent payment of {a}? Our usual approver is out; I'll sign off afterwards."]).format(a=amt())
        add("Malicious", "BEC (CFO wire request)", "VM5", "medium", "Attacker poses as the CFO to obtain an urgent wire.",
            "free-mail with the CFO's name" if free else "spoofed internal address failing DMARC",
            payload(frm, p(["Wire today", "Confidential", "Urgent payment"]), html(body, f"{name.split()[0]}"), auth_results=a,
                    relationship=rel(sent=0 if free else 6, names=[f"{local}@{ORG}"] if free else ())))


def m_w2(n):
    for i in range(n):
        name, local = CEO
        body = p(["Please send me the W-2 forms for all employees as PDFs today, I need them for a review.",
                  "Can you export the full payroll report with SSNs and email it to me? Need it before my meeting.",
                  "Send me the employee tax documents for this year, all staff, as soon as you can."])
        add("Malicious", "data-theft BEC (W-2 / payroll data)", "VM6", "hard", "Attacker poses as the CEO to steal employee tax data.",
            "free-mail address with the CEO's name; no money request",
            payload(f"{name} <{local}.office@{p(FREE)}>", p(["Request", "W-2s", "Quick request"]), html(body, name.split()[0]),
                    auth_results=auth("gmail.com"), relationship=rel(names=[f"{local}@{ORG}"])))


def m_mfa_fatigue(n):
    for i in range(n):
        dom = p(["lattice-it-support.example", "it-securedesk.example"])
        body = p(["We are fixing a sync issue on your account. You will get a login prompt on your phone - please approve it.",
                  "During today's maintenance please accept any sign-in request you receive; it's us.",
                  "Reply with the number shown in your authenticator app so we can finish the migration."])
        add("Malicious", "MFA fatigue / push approval", "VM7", "hard", "Attacker asks the victim to approve an MFA prompt or share a number-match code.",
            "unfamiliar IT-themed sender",
            payload(f"IT Service Desk <servicedesk@{dom}>", p(["Account maintenance", "MFA migration", "Sign-in prompt"]), html(body),
                    auth_results=auth(dom), relationship=rel()))


def m_vendor_compromise(n):
    for i in range(n):
        vname, vdom, box = VENDORS[i % 2]
        frm = f"{vname} <{box}@{vdom}>"
        prior = {"from_header": frm, "reply_to": None, "auth_result": auth(vdom), "participants": [f"ap@{ORG}"]}
        body = p(["As discussed, please make this month's payment to our new account below; the previous one is being closed.",
                  "Small update before you pay: we changed banks last week. New details are in the attached letter.",
                  "Our finance team asked me to share updated payment details. Please use them for the open invoices."])
        add("Malicious", "vendor email compromise (real vendor mailbox)", "VM8", "hard",
            "Real vendor mailbox is compromised; attacker changes payment details inside the existing thread.",
            "known, authenticated vendor in an existing thread; no header anomaly",
            payload(frm, f"Re: {p(['Order', 'Shipment', 'Invoice'])} {R.randint(100, 999)}", html(body, vname), auth_results=auth(vdom),
                    thread=[prior], in_reply_to=f"<{R.randint(10**6, 10**7)}@{vdom}>", relationship=rel(sent=5)))


def m_new_attachments(n):
    files = [("Meeting_Notes.one", "application/onenote"), ("Archive.vhd", "application/octet-stream"),
             ("Manual.chm", "application/vnd.ms-htmlhelp"), ("Update.hta", "application/hta"),
             ("invoice_‮fdp.exe", "application/octet-stream"), ("Addin.xll", "application/octet-stream"),
             ("Docs.rar", "application/vnd.rar"), ("Setup.wsf", "text/xml")]
    for i in range(n):
        f, t = files[i % 8]
        dom = p(["shared-notes-hub.example", "docs-dispatch.example", "file-courier.example"])
        body = "Please open the attached file. Password: 7781." if f.endswith(".rar") else p(["Please review the attached.", "See attachment.", "Notes from today attached."])
        add("Malicious", "malicious attachment (new file types)", "VM9", "medium", f"Unknown sender delivers a malicious {f.rsplit('.', 1)[-1]} file.",
            "unfamiliar sender",
            payload(f"{p(['Documents', 'Notes', 'Courier'])} <send@{dom}>", p(["Shared notes", "Document", "File"]), html(body), auth_results=auth(dom),
                    attachments=[(f, t, R.randint(20000, 3000000))], relationship=rel()))


def m_partner_compromise(n):
    for i in range(n):
        name, local, dom = PARTNERS[i % 3]
        evil = p(["quillstone-docs-share.example", "secure-doc-preview.example", "fileshare-cloud-view.example"])
        body = p(["Sharing the revised SOW for your review.", "Please review the attached proposal before Thursday.",
                  "I've uploaded the contract; you'll need to sign in with your email to access it."])
        add("Malicious", "compromised partner mailbox", "VM10", "hard", f"{name}'s real mailbox is compromised and sends a phishing link.",
            "known, authenticated partner; link to a never-seen domain",
            payload(f"{name} <{local}@{dom}>", p(["Revised SOW", "Proposal", "Contract"]), html(body, links=[(p(["Open", "View file", "Review"]), f"https://{evil}/f/{R.randint(100, 999)}")]),
                    auth_results=auth(dom), relationship=rel(sent=R.randint(2, 8))))


def m_investment(n):
    for i in range(n):
        dom = p(["alpha-yield-club.example", "crypto-rewards-desk.example", "staff-bonus-program.example"])
        body = p(["Exclusive for {o} staff: double your crypto in 7 days. Send 0.1 BTC to the wallet below to join.",
                  "You've won a $500 staff bonus. Pay the $25 processing fee via the link to claim it.",
                  "Limited spots: invest today and receive guaranteed 20% monthly returns."]).format(o="Lattice")
        add("Malicious", "investment / prize scam", "VM11", "medium", "Fraudulent investment or prize offer.", "unfamiliar sender",
            payload(f"Rewards Team <offers@{dom}>", p(["Exclusive offer", "You won", "Last spots"]), html(body, links=[("Claim", f"https://{dom}/claim")]),
                    auth_results=auth(dom), relationship=rel()))


def m_evasion2(n):
    variants = [
        ("punycode link text", html("Please verify your Microsoft account.", links=[("https://xn--microsft-q0a.com/login", "https://xn--microsft-q0a.com/login")])),
        ("text split by inline spans", "<p>Our <span>ba</span><span>nk</span> det<span>ails</span> changed; please wi<span>re</span> the payment to our new acc<span>ount</span>.</p>"),
        ("whitespace padding before link", html("Statement attached." + "&nbsp;" * 200, links=[("Download", "https://statement-files-cdn.example/s")])),
        ("RTL override in filename", html("Please find the invoice attached.")),
        ("request in subject only", html("See subject.")),
        ("lookalike in link text only", html("Your package is waiting.", links=[("www.fedex.com/track", "https://fedex.com.track-pkg.example/t")])),
        ("benign-looking greeting then hidden link", html("Thanks for the meeting today!", hidden='<a href="https://cred-harvest.example">verify</a> sign in')),
    ]
    for i in range(n):
        name, body = variants[i % 7]
        dom = p(["notice-relay.example", "statement-files-cdn.example", "acct-review-hub.example"])
        atts = [("invoice_‮fdp.exe", "application/octet-stream", 400000)] if name == "RTL override in filename" else ()
        subj = "Wire the payment to our new account today" if name == "request in subject only" else p(["Notice", "Update", "Statement"])
        add("Malicious", "evasion attempt (new techniques)", "VM12", "hard", f"Attack using an evasion technique: {name}.", name,
            payload(f"{p(['Notice', 'Accounts', 'Delivery'])} <info@{dom}>", subj, body, auth_results=auth(dom), attachments=atts, relationship=rel()))


def m_internal_lookalike(n):
    for i in range(n):
        dom = p(["lattice-dynarnics.example", "latticedynamics.example", "lattice-dynamic.example", "iattice-dynamics.example"])
        body = p(["Your mailbox will be migrated tonight. Sign in to keep your data.", "Please review the attached updated org chart.",
                  "IT here - please confirm your password on the portal before the upgrade."])
        add("Malicious", "internal-domain look-alike", "VM13", "medium", "Attacker uses a look-alike of the company's own domain.",
            "look-alike of the organization's domain",
            payload(f"IT Support <it@{dom}>", p(["Mailbox migration", "Org chart", "Upgrade"]), html(body, links=[("Portal", f"https://{dom}/portal")]),
                    auth_results=auth(dom), relationship=rel()))


# ================================================================== LEGITIMATE (100)
def l_projects(n):
    for i in range(n):
        name, local, dom = PARTNERS[i % 3]
        body = p(["Attached is the revised timeline; the main change is the QA window.", "Thanks for the quick turnaround. Two notes on section 3.",
                  "Can we push our sync to 3pm? Something came up.", "Great call today. Summary and next steps below."])
        th = [{"from_header": f"{name} <{local}@{dom}>", "reply_to": None, "auth_result": auth(dom), "participants": [f"me@{ORG}"]}] if i % 2 else []
        add("Legitimate", "project collaboration", "VL1", "easy", "Ordinary collaboration with a known partner.", "known partner",
            payload(f"{name} <{local}@{dom}>", ("Re: " if th else "") + p(["Timeline", "Notes", "Sync", "Summary"]), html(body, name.split()[0]),
                    auth_results=auth(dom), thread=th, in_reply_to=f"<x@{dom}>" if th else None, relationship=rel(sent=R.randint(2, 20))))


def l_escrow_legit(n):
    for i in range(n):
        name, local, dom = PARTNERS[1]
        body = p(["Closing is confirmed for Tuesday. Wiring instructions will come only by phone from our office; never act on emailed instructions.",
                  "Please call our office at the number on our website to receive wiring instructions for the closing.",
                  "Reminder: we will never change wiring instructions by email. Call us to confirm before sending any funds."])
        add("Legitimate", "legitimate escrow / closing notice", "VL2", "hard", "Known law firm warns that wiring instructions are only given by phone.",
            "known, authenticated law firm",
            payload(f"{name} <{local}@{dom}>", p(["Closing confirmed", "Closing logistics", "Wiring reminder"]), html(body, name), auth_results=auth(dom),
                    relationship=rel(sent=4)))


def l_hr_vendor(n):
    for i in range(n):
        body = p(["Open enrollment starts Monday. Review your plan options in the benefits portal.", "Your updated benefits summary is available in your account.",
                  "Reminder: submit dependent verification documents by March 1."])
        add("Legitimate", "HR / benefits provider notice", "VL3", "medium", "Known benefits provider notice with links on its own domain.",
            "known provider domain",
            payload("BenefitsFlow <notices@benefitsflow.example>", p(["Open enrollment", "Benefits summary", "Reminder"]),
                    html(body, links=[("Open portal", "https://benefitsflow.example/portal")]), auth_results=auth("benefitsflow.example"), relationship=rel(sent=1)))


def l_saas(n):
    items = [("Jira <jira@lattice.atlassian.net>", "[PROJ-412] Status changed to Done", "atlassian.net", "https://lattice.atlassian.net/browse/PROJ-412"),
             ("GitHub <notifications@github.com>", "[lattice/api] PR #88 approved", "github.com", "https://github.com/lattice/api/pull/88"),
             ("Slack <feedback@slack.com>", "Your weekly Slack digest", "slack.com", "https://lattice.slack.com/digest"),
             ("Figma <no-reply@figma.com>", "Hannah commented on Onboarding v3", "figma.com", "https://www.figma.com/file/x")]
    for i in range(n):
        frm, subj, dom, url = items[i % 4]
        add("Legitimate", "SaaS notification", "VL4", "easy", "Genuine SaaS notification linking to its own service.", "bulk-style notification",
            payload(frm, subj, html("You have a new update.", links=[("View", url)]), auth_results=auth(dom), bulk=True, relationship=rel()))


def l_ap_routine(n):
    for i in range(n):
        vname, vdom, box = VENDORS[i % 4]
        k = i % 3
        if k == 0:
            frm, dom, body = f"{vname} <{box}@{vdom}>", vdom, f"Payment received for invoice {R.randint(1000, 9999)}. Thank you!"
        elif k == 1:
            name, local = PEOPLE[i % 6]
            frm, dom, body = f"{name} <{local}@{ORG}>", ORG, f"Approved the {vname} PO for {amt()}. Please process in the next run."
        else:
            frm, dom, body = f"{vname} <{box}@{vdom}>", vdom, "Remittance advice attached for your records."
        add("Legitimate", "routine accounts-payable", "VL5", "easy", "Routine payment confirmation or internal approval; no detail changes.",
            "known sender", payload(frm, p(["Payment received", "PO approval", "Remittance advice"]), html(body), auth_results=auth(dom),
                                    relationship=rel(sent=R.randint(3, 15)), attachments=[("remittance.pdf", "application/pdf", 40000)] if k == 2 else ()))


def l_exec_benign(n):
    for i in range(n):
        name, local = (CEO if i % 2 else CFO)
        body = p(["Jump on the board prep call now if you can - link in the calendar invite.", "Send me the latest revenue deck before 4pm please.",
                  "Urgent: I need the hiring plan numbers for tomorrow's offsite.", "Can you confirm the offsite headcount today?"])
        add("Legitimate", "urgent request from an executive (benign)", "VL6", "medium", "Genuine urgent internal request; nothing irreversible or secret.",
            "known internal executive", payload(f"{name} <{local}@{ORG}>", p(["Urgent", "Today", "Quick ask"]), html(body, name.split()[0]),
                                                auth_results=auth(ORG), relationship=rel(sent=R.randint(5, 30))))


def l_security_team(n):
    texts = ["Heads-up: this week's phishing simulation will mimic a fake invoice portal. Report anything suspicious.",
             'Real example we blocked: "Please send me the W-2 forms for all employees." Never send tax data by email.',
             "We will never ask you to approve an MFA prompt you didn't trigger. Deny it and tell us.",
             "Wire fraud alert: criminals claim their bank details changed and ask you to pay a new account. Always call back."]
    for i in range(n):
        add("Legitimate", "internal security awareness", "VL7", "hard", "Security team education quoting or describing attacks.",
            "known internal sender", payload(f"Security Team <security@{ORG}>", p(["Security update", "Awareness", "Fraud alert"]),
                                             html(texts[i % 4]), auth_results=auth(ORG), relationship=rel(sent=2)))


def l_support(n):
    for i in range(n):
        frm = p(["Nimbus Support <support@nimbusofficesupply.example>", "Copperline Help <help@copperline-freight.example>"])
        dom = frm.split("@")[1].rstrip(">")
        add("Legitimate", "customer support with platform Reply-To", "VL8", "medium", "Vendor support replies through a ticketing platform.",
            "ticketing Reply-To", payload(frm, f"Re: [Case {R.randint(10000, 99999)}] {p(['Order', 'Delivery', 'Billing question'])}",
                                          html(p(["We've updated your case.", "Your replacement ships tomorrow.", "Refund processed."])), auth_results=auth(dom),
                                          reply_to=f"support@{dom.split('.')[0]}.casemanager-platform.example", in_reply_to=f"<c@{dom}>", relationship=rel(sent=2)))


def l_travel(n):
    items = [("SkyRoute <bookings@skyroute.example>", "Your flight confirmation", "skyroute.example"),
             ("StayWell Hotels <reservations@staywell.example>", "Reservation confirmed", "staywell.example"),
             ("ParcelPoint <tracking@parcelpoint.example>", "Your package is out for delivery", "parcelpoint.example"),
             ("RideNow <receipts@ridenow.example>", "Your trip receipt", "ridenow.example"),
             ("CloudSuite <billing@cloudsuite.example>", "Your monthly receipt", "cloudsuite.example")]
    for i in range(n):
        frm, subj, dom = items[i % 5]
        add("Legitimate", "travel / receipts / shipping", "VL9", "easy", "Transactional email from a legitimate service.", "unfamiliar but authenticated service",
            payload(frm, subj, html(p(["Details below.", "Thanks for choosing us.", "Track or manage your booking online."]), links=[("Manage", f"https://{dom}/m/{R.randint(1, 999)}")]),
                    auth_results=auth(dom), bulk=i % 2 == 0, relationship=rel()))


def l_cold_outreach(n):
    for i in range(n):
        frm = p(["Nadia Cole <nadia@growthpilot-sales.example>", "Ben Ortiz <ben.ortiz@talentscope.example>", "Mira Sato <mira@datapipe-solutions.example>"])
        dom = frm.split("@")[1].rstrip(">")
        body = p(["I noticed Lattice is hiring data engineers - would a short intro call be useful?", "We help teams like yours cut cloud costs. Worth a chat?",
                  "I'm recruiting for a senior role that matches your profile. Happy to share details."])
        add("Legitimate", "cold outreach (sales / recruiting)", "VL10", "medium", "Unsolicited but benign first-contact outreach.", "unfamiliar sender",
            payload(frm, p(["Quick intro", "Idea for Lattice", "Opportunity"]), html(body), auth_results=auth(dom), relationship=rel()))


def l_it_sso(n):
    for i in range(n):
        body = p(["We're moving to single sign-on. Sign in to your Okta dashboard to activate your account.",
                  "Your password expires in 7 days. Sign in to the company portal to update it.",
                  "New expense tool: sign in with your work account to get started."])
        url = p(["https://lattice.okta.com/app/dashboard", f"https://sso.{ORG}/login", "https://lattice.expensely-app.example/login"])
        add("Legitimate", "internal IT notice with SSO link", "VL11", "hard", "Genuine internal IT notice linking to the company's identity provider or SaaS.",
            "known internal sender; link to an SSO/SaaS domain", payload(f"IT Team <it@{ORG}>", p(["SSO rollout", "Password expiry", "New tool"]),
                                                                        html(body, links=[("Sign in", url)]), auth_results=auth(ORG), relationship=rel(sent=3)))


def l_forwards(n):
    for i in range(n):
        name, local = PEOPLE[i % 6]
        inner = p(["Copperline Freight: please note our new warehouse address from April 1.", "Conference agenda: keynote at 9am, workshops after lunch.",
                   "Nimbus: your order 4412 has shipped.", "Arbor Legal: closing documents are ready for signature at our office."])
        add("Legitimate", "colleague forwards a benign message", "VL12", "medium", "Colleague forwards ordinary third-party content.", "known internal sender",
            payload(f"{name} <{local}@{ORG}>", "Fwd: " + p(["FYI", "agenda", "shipping", "closing docs"]),
                    html(p(["FYI", "See below.", "For your records."]), "---------- Forwarded message ----------", inner), auth_results=auth(ORG),
                    relationship=rel(sent=R.randint(5, 20))))


PLAN = [(m_escrow, 9), (m_invoice_portal, 8), (m_notification_lure, 10), (m_hr_policy, 8), (m_cfo_wire, 8), (m_w2, 6), (m_mfa_fatigue, 6),
        (m_vendor_compromise, 8), (m_new_attachments, 8), (m_partner_compromise, 8), (m_investment, 6), (m_evasion2, 7), (m_internal_lookalike, 8),
        (l_projects, 10), (l_escrow_legit, 6), (l_hr_vendor, 8), (l_saas, 10), (l_ap_routine, 10), (l_exec_benign, 8), (l_security_team, 8),
        (l_support, 8), (l_travel, 10), (l_cold_outreach, 8), (l_it_sso, 6), (l_forwards, 8)]

if __name__ == "__main__":
    for fn, n in PLAN:
        fn(n)
    cases = v1.CASES
    for i, c in enumerate(cases, 1):
        c["id"] = f"H{i:03d}"
    labs = [c["label"] for c in cases]
    assert labs.count("Malicious") == 100 and labs.count("Legitimate") == 100, (labs.count("Malicious"), labs.count("Legitimate"))
    with OUT.open("w") as fh:
        for c in cases:
            fh.write(json.dumps({k: c[k] for k in ("id", "label", "category", "family", "difficulty", "rationale", "context", "input")}) + "\n")
    print(f"wrote {len(cases)} cases to {OUT}")
