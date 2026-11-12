"""Phase 5c v3 HOLDOUT generator (seed 90731). Written AFTER the engine freeze (eval/v3/FREEZE.md) and
before any v3 run. New organization, people, vendors and scenario types that appear in neither v1 nor v2.
Only neutral email-building helpers are shared. Labels come from each scenario's intent.
"""

import importlib.util
import json
import random
from pathlib import Path

_spec = importlib.util.spec_from_file_location("v1gen", Path(__file__).resolve().parents[1] / "v1" / "generate.py")
v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v1)

R = random.Random(90731)
v1.RNG = R
v1.CASES.clear()
v1._TOKENS.clear()
OUT = Path(__file__).with_name("dataset.jsonl")
auth, payload, html, add = v1.auth, v1.payload, v1.html, v1.add

ORG = "vantorbio.example"
STAFF = [("Rachel Stone", "rachel.stone"), ("Diego Alvarez", "diego.alvarez"), ("Nina Petrova", "nina.petrova"),
         ("Leo Grant", "leo.grant"), ("Amara Obi", "amara.obi"), ("Theo Lambert", "theo.lambert")]
CEO, CFO, BOARD = ("Sofia Marin", "sofia.marin"), ("Daniel Kerr", "daniel.kerr"), ("Helen Ashby", "helen.ashby")
VENDORS = [("Helix Reagents", "helixreagents.example", "ar"), ("Bluefin Couriers", "bluefin-couriers.example", "billing"),
           ("Keystone Audit", "keystoneaudit.example", "confirmations"), ("Summit Facilities", "summitfacilities.example", "accounts")]
PARTNERS = [("Ines Duarte", "ines.duarte", "helixreagents.example"), ("Owen Price", "owen.price", "keystoneaudit.example"),
            ("Kai Mori", "kai.mori", "summitfacilities.example")]
KNOWN = [ORG] + [v[1] for v in VENDORS] + ["procurewise.example"]
FREE = ["gmail.com", "outlook.com", "icloud.com", "proton.me", "yahoo.com"]


def rel(sent=0, names=()):
    return {"window_days": 180, "known_domains": KNOWN, "sender_sent_count": sent, "name_match_addresses": list(names)}


def p(seq):
    return R.choice(seq)


def num():
    return f"+1 ({R.randint(200, 989)}) {R.randint(200, 989)}-{R.randint(1000, 9999)}"


# ================================================================== MALICIOUS (100)
def m_callback(n):  # TOAD: no link, phone number only
    for i in range(n):
        dom = p(["renewal-billing-center.example", "geek-protect-desk.example", "order-dispute-team.example"])
        body = p(["Your annual protection plan renewed for $499.99. If you did not authorize this, call {n} within 24 hours to cancel.",
                  "We detected an order of 3 laptops on your account. To dispute the charge, call our team at {n}.",
                  "Your subscription will auto-renew today. Call {n} to request a refund."]).format(n=num())
        add("Malicious", "callback phishing (phone, no link)", "XM1", "hard", "Fake charge notice that pushes the victim to call an attacker-run phone line.",
            "unfamiliar sender; no link", payload(f"Billing Center <billing@{dom}>", p(["Renewal receipt", "Order confirmation", "Subscription notice"]),
                                                   html(body), auth_results=auth(dom), relationship=rel()))


def m_legal(n):
    for i in range(n):
        dom = p(["legal-notice-office.example", "copyright-claims-desk.example", "court-filings-portal.example"])
        body = p(["You are named in a subpoena. Download and review the attached court documents within 48 hours.",
                  "A copyright infringement complaint was filed against your website. View the evidence at the link below.",
                  "Final notice of legal action. Sign in to the case portal to submit your response."])
        att = [("Subpoena_Documents.zip", "application/zip", 210000)] if i % 2 == 0 else ()
        add("Malicious", "fake legal / copyright notice", "XM2", "medium", "Intimidating fake legal notice delivering malware or a credential page.",
            "unfamiliar sender; threat of legal action",
            payload(f"{p(['Legal Department', 'Claims Office', 'Court Notices'])} <notices@{dom}>", p(["Subpoena", "Copyright complaint", "Final notice"]),
                    html(body, links=() if att else [("View case", f"https://{dom}/case/{R.randint(1000, 9999)}")]), auth_results=auth(dom),
                    attachments=att, relationship=rel()))


def m_onboarding(n):
    for i in range(n):
        dom = p(["vendor-registration-hub.example", "supplier-onboard-forms.example", "vantor-supplier-portal.example"])
        body = p(["As part of supplier onboarding, please complete the form with your company bank account and tax ID.",
                  "To finish your vendor registration, upload your banking details and signed W-9 at the portal.",
                  "Please confirm your remittance account in the supplier form so payments are not delayed."])
        add("Malicious", "fake vendor onboarding form", "XM3", "medium", "Attacker collects banking and tax details through a fake onboarding form.",
            "unfamiliar sender posing as procurement",
            payload(f"Supplier Onboarding <procurement@{dom}>", p(["Supplier registration", "Vendor onboarding", "Action required"]),
                    html(body, links=[("Open form", f"https://{dom}/form")]), auth_results=auth(dom), relationship=rel()))


def m_audit(n):
    for i in range(n):
        name, local, dom = PARTNERS[1]
        fake = p(["keystone-audit.example", "keystoneaudit-confirm.example", "keyst0neaudit.example"])
        body = p(["As part of the year-end audit, please confirm your outstanding balance and remit the difference to the account in the attached letter.",
                  "Please sign in to our confirmation portal with your email credentials to confirm the balances.",
                  "Kindly confirm receivables by replying with your latest bank statements."])
        add("Malicious", "fake audit confirmation", "XM4", "medium", "Impersonated audit firm requests payment, credentials or statements.",
            "imitation of the known audit firm's domain",
            payload(f"{name} <{local}@{fake}>", p(["Audit confirmation", "Year-end audit", "Balance confirmation"]), html(body, name),
                    auth_results=auth(fake), relationship=rel(), attachments=[("confirmation_letter.pdf", "application/pdf", 50000)] if i % 2 else ()))


def m_board(n):
    for i in range(n):
        name, local = BOARD
        body = p(["I'm reviewing the acquisition before the board call. Please email me the full due-diligence data room export tonight.",
                  "Send me the cap table and the list of all employee equity grants, I need it urgently.",
                  "Forward me the payroll report and executive compensation file before tomorrow morning."])
        add("Malicious", "board-member impersonation (data request)", "XM5", "hard", "Attacker poses as a board member to obtain confidential data.",
            "free-mail address with a board member's name",
            payload(f"{name} <{local}.board@{p(FREE)}>", p(["Board prep", "Confidential", "Need this tonight"]), html(body, name.split()[0]),
                    auth_results=auth("gmail.com"), relationship=rel(names=[f"{local}@{ORG}"])))


def m_agent(n):
    for i in range(n):
        dom = p(["vantorbio-itsupport.example", "endpoint-protect-update.example", "security-agent-deploy.example"])
        body = p(["All laptops must install the new security agent today. Download and run the installer from the link below.",
                  "Your device is missing a mandatory update. Install the remote support tool so we can patch it.",
                  "Please run the attached agent installer; it takes two minutes."])
        att = [("SecurityAgent_Setup.exe", "application/octet-stream", 3_100_000)] if "attached" in body else ()
        add("Malicious", "fake IT agent / remote-tool install", "XM6", "medium", "Attacker gets malware or remote access installed under an IT pretext.",
            "unfamiliar IT-themed sender",
            payload(f"IT Operations <itops@{dom}>", p(["Mandatory update", "Security agent", "Device compliance"]),
                    html(body, links=() if att else [("Download", f"https://{dom}/agent.pkg")]), auth_results=auth(dom), attachments=att, relationship=rel()))


def m_tax_refund(n):
    for i in range(n):
        dom = p(["tax-refund-claims-office.example", "revenue-service-refunds.example"])
        body = p(["You are eligible for a tax refund of $1,240. Submit your bank details on the refund page to receive it.",
                  "Your refund is pending. Verify your identity and banking information to release the payment.",
                  "Claim your refund before Friday by confirming your account number on our portal."])
        add("Malicious", "tax refund scam", "XM7", "medium", "Fake tax authority collects banking and identity details.",
            "unfamiliar sender posing as a tax authority",
            payload(f"Refund Department <refunds@{dom}>", p(["Tax refund", "Refund pending", "Claim your refund"]),
                    html(body, links=[("Claim refund", f"https://{dom}/claim")]), auth_results=auth(dom), relationship=rel()))


def m_job_check(n):
    for i in range(n):
        frm = p(["Talent Acquisition <offers@globalhire-careers.example>", "HR Recruiter <recruiter.jobs@outlook.com>"])
        dom = frm.split("@")[1].rstrip(">")
        body = p(["Congratulations on your remote role! We will mail you a check for equipment; deposit it and send the balance to our vendor.",
                  "To start, purchase your equipment from our approved supplier using the funds we transfer, then send the rest back.",
                  "Your offer is attached. Please send a copy of your passport and bank details to set up payroll."])
        add("Malicious", "fake job offer / check scam", "XM8", "medium", "Fake job offer leading to money mule activity or identity theft.",
            "unfamiliar sender", payload(frm, p(["Job offer", "Welcome aboard", "Next steps"]), html(body), auth_results=auth(dom), relationship=rel()))


def m_charity(n):
    for i in range(n):
        dom = p(["relief-fund-now.example", "disaster-aid-appeal.example"])
        body = p(["Families affected by the floods need help today. Donate via the link; every gift is matched.",
                  "Urgent appeal: send a donation by gift card or crypto to reach victims faster.",
                  "Support the relief effort - transfer your donation to the wallet below."])
        add("Malicious", "fake charity appeal", "XM9", "medium", "Fraudulent charity collecting untraceable payments.", "unfamiliar sender",
            payload(f"Relief Appeal <give@{dom}>", p(["Urgent appeal", "Help today", "Relief effort"]), html(body, links=[("Donate", f"https://{dom}/give")]),
                    auth_results=auth(dom), relationship=rel()))


def m_calendar(n):
    for i in range(n):
        dom = p(["meeting-invites-sync.example", "calendar-share-center.example"])
        body = p(["You have been invited to 'Q3 Budget Review'. Sign in to accept the invitation.",
                  "Updated invitation: Compensation planning. View the agenda and log in to RSVP.",
                  "Meeting moved. Please re-authenticate to see the new time."])
        add("Malicious", "calendar-invite phishing", "XM10", "medium", "Fake meeting invite leading to a credential page.", "unfamiliar sender",
            payload(f"Calendar <invites@{dom}>", p(["Invitation: Q3 Budget Review", "Updated invitation", "Meeting moved"]),
                    html(body, links=[("Accept", f"https://{dom}/rsvp")]), auth_results=auth(dom), relationship=rel()))


def m_refund_support(n):
    for i in range(n):
        dom = p(["refund-helpdesk-online.example", "support-refunds-team.example"])
        body = p(["We overcharged you by mistake. To receive your $350 refund, install our support app so an agent can process it.",
                  "Your refund failed. Reply with your card number and expiry date to retry.",
                  "To complete your refund, read us the code we text to your phone."])
        add("Malicious", "refund / tech-support scam", "XM11", "medium", "Scammer uses a refund pretext to obtain remote access, card data or an OTP.",
            "unfamiliar sender", payload(f"Refund Support <help@{dom}>", p(["Refund", "Overcharge", "Refund failed"]), html(body),
                                         auth_results=auth(dom), relationship=rel()))


def m_vendor_hijack(n):
    for i in range(n):
        vname, vdom, box = VENDORS[i % 2]
        frm = f"{vname} <{box}@{vdom}>"
        prior = {"from_header": frm, "reply_to": None, "auth_result": auth(vdom), "participants": [f"ap@{ORG}"]}
        rt = f"{vname} <{box}@{vdom.split('.')[0]}-accounts.example>" if i % 2 else None
        body = p(["Quick note before your next run: payments should now go to our account at a different bank; details attached.",
                  "Please hold the payment to our old account and use the new instructions I'll send shortly.",
                  "Following our call, here are the updated wire instructions for invoices going forward."])
        add("Malicious", "vendor thread hijack (new wording)", "XM12", "hard", "Payment redirection inside an existing vendor thread.",
            "existing thread" + ("; Reply-To added" if rt else ""),
            payload(frm, f"Re: Invoice {R.randint(1000, 9999)}", html(body, vname), auth_results=auth(vdom), reply_to=rt, thread=[prior],
                    in_reply_to=f"<{R.randint(10**6, 10**7)}@{vdom}>", relationship=rel(sent=4)))


def m_sms_pivot(n):
    for i in range(n):
        name, local = CEO
        body = p(["I'm in back-to-back meetings. Text me your cell number, I need your help with something sensitive.",
                  "Can you move this to Signal? I'll explain there - please keep it to yourself for now.",
                  "Are you around? Reply with your WhatsApp, need a favor before noon."])
        add("Malicious", "executive pivot to SMS / chat", "XM13", "medium", "Attacker poses as the CEO to move the victim to an unmonitored channel.",
            "free-mail with the CEO's name", payload(f"{name} <{local}.exec@{p(FREE)}>", p(["Quick one", "Need you", "Are you around?"]),
                                                    html(body, name.split()[0]), auth_results=auth("gmail.com"), relationship=rel(names=[f"{local}@{ORG}"])))


# ================================================================== LEGITIMATE (100)
def l_audit(n):
    for i in range(n):
        name, local, dom = PARTNERS[1]
        body = p(["As part of the year-end audit, please confirm the attached balances through your usual portal; no payment is needed.",
                  "Our team will be on site Monday. Please have the fixed-asset register ready.",
                  "Thanks for the confirmations - we'll share the draft findings next week."])
        add("Legitimate", "real auditor correspondence", "XL1", "hard", "Known audit firm's routine audit communication.", "known, authenticated firm",
            payload(f"{name} <{local}@{dom}>", p(["Audit confirmation", "On-site visit", "Draft findings"]), html(body, name), auth_results=auth(dom), relationship=rel(sent=5)))


def l_procurement(n):
    for i in range(n):
        body = p(["Your supplier profile update was approved.", "Please approve the purchase request PR-{x} in ProcureWise.",
                  "A new supplier onboarding task is assigned to you in ProcureWise."]).format(x=R.randint(1000, 9999))
        add("Legitimate", "procurement system notification", "XL2", "medium", "Known procurement platform workflow email; links on its own domain.",
            "known platform", payload("ProcureWise <notifications@procurewise.example>", p(["Request approved", "Approval needed", "New task"]),
                                      html(body, links=[("Open", "https://procurewise.example/app")]), auth_results=auth("procurewise.example"), relationship=rel(sent=1)))


def l_courier(n):
    for i in range(n):
        frm, dom = p([("DHL Express <noreply@dhl.com>", "dhl.com"), ("Bluefin Couriers <billing@bluefin-couriers.example>", "bluefin-couriers.example")])
        body = p(["Import duties of $86.20 apply to shipment {x}. Pay on our website or at delivery.", "Your shipment {x} is out for delivery today.",
                  "Invoice for courier services in October is attached."]).format(x=R.randint(10**8, 10**9))
        add("Legitimate", "courier notice / customs invoice", "XL3", "medium", "Genuine courier notification or invoice.", "authenticated courier",
            payload(frm, p(["Shipment update", "Duties due", "Monthly invoice"]), html(body, links=[("Track", f"https://{dom}/track")]),
                    auth_results=auth(dom), relationship=rel(sent=1 if "bluefin" in dom else 0)))


def l_it_rollout(n):
    for i in range(n):
        body = p(["We're rolling out the new endpoint agent. It installs automatically via Self Service; no action needed.",
                  "Please restart your laptop tonight to finish the security update.",
                  "Install the VPN client from the company portal before your trip."])
        add("Legitimate", "internal IT rollout", "XL4", "hard", "Genuine internal IT rollout using the company's own portal.", "known internal sender",
            payload(f"IT Operations <itops@{ORG}>", p(["Endpoint agent", "Restart tonight", "VPN client"]),
                    html(body, links=[("Company portal", f"https://portal.{ORG}/self-service")]), auth_results=auth(ORG), relationship=rel(sent=4)))


def l_approvals(n):
    for i in range(n):
        name, local = STAFF[i % 6]
        body = p(["Please approve my leave request for next Friday in the HR system.", "Can you approve the expense report I submitted yesterday?",
                  "Approve the PO for lab supplies when you get a chance."])
        add("Legitimate", "internal approval request", "XL5", "medium", "Colleague asks for an ordinary workflow approval.", "known internal sender",
            payload(f"{name} <{local}@{ORG}>", p(["Approval", "Leave request", "Expense report"]), html(body, name.split()[0]), auth_results=auth(ORG),
                    relationship=rel(sent=R.randint(4, 25))))


def l_charity_internal(n):
    for i in range(n):
        body = p(["Our annual food drive starts Monday - drop donations at reception.", "Join the charity run on Saturday! Sign up on the intranet.",
                  "We matched $12,000 in employee donations this year. Thank you!"])
        add("Legitimate", "internal charity / community", "XL6", "easy", "Internal community announcement.", "known internal sender",
            payload(f"People Team <people@{ORG}>", p(["Food drive", "Charity run", "Thank you"]), html(body), auth_results=auth(ORG), relationship=rel(sent=2)))


def l_partner_work(n):
    for i in range(n):
        name, local, dom = PARTNERS[i % 3]
        body = p(["Lot 2231 shipped this morning; COA attached.", "Can we reschedule the maintenance window to Thursday?",
                  "I shared the updated spec in our Box folder.", "Please find the signed quote attached."])
        links = [("Box folder", "https://app.box.com/folder/123")] if "Box" in body else []
        add("Legitimate", "partner / vendor work email", "XL7", "easy", "Ordinary partner correspondence.", "known partner",
            payload(f"{name} <{local}@{dom}>", p(["Shipment", "Maintenance", "Spec", "Quote"]), html(body, name.split()[0], links=links),
                    auth_results=auth(dom), relationship=rel(sent=R.randint(3, 15))))


def l_exec(n):
    for i in range(n):
        name, local = (CEO if i % 2 else CFO)
        body = p(["Board deck draft is in the shared drive; comments by EOD please.", "Please send me the Q3 forecast before the 3pm call.",
                  "Can you join the investor call in 10 minutes?"])
        add("Legitimate", "executive request (benign)", "XL8", "medium", "Genuine executive request; nothing secret or irreversible.", "known internal executive",
            payload(f"{name} <{local}@{ORG}>", p(["Board deck", "Forecast", "Investor call"]), html(body, name.split()[0]), auth_results=auth(ORG), relationship=rel(sent=10)))


def l_security_notes(n):
    for i in range(n):
        body = p(['Scam alert: callers claiming to be "billing" ask you to call back about a renewal. Never call numbers from unexpected emails.',
                  "Reminder: IT will never ask you to install software from an email link. Use Self Service.",
                  "Fake job offers that send you a check are a common money-mule scam. Don't deposit and forward funds."])
        add("Legitimate", "internal security awareness (new topics)", "XL9", "hard", "Security education describing scams.", "known internal sender",
            payload(f"Security <security@{ORG}>", p(["Scam alert", "Reminder", "Awareness"]), html(body), auth_results=auth(ORG), relationship=rel(sent=2)))


def l_newsletters(n):
    for i in range(n):
        frm, dom = p([("BioWeekly <news@bioweekly.example>", "bioweekly.example"), ("LabGear Deals <deals@labgear.example>", "labgear.example"),
                      ("Conference Team <info@synbio-summit.example>", "synbio-summit.example")])
        body = p(["This week: CRISPR delivery advances and funding news.", "Final days: 20% off pipettes. Shop now.",
                  "Your speaker slot is confirmed. Upload your slides by Oct 1."])
        add("Legitimate", "newsletter / conference / deals", "XL10", "easy", "Legitimate bulk or event email.", "bulk",
            payload(frm, p(["Weekly", "Final days", "Speaker confirmation"]), html(body, links=[("Read", f"https://{dom}/x")]), auth_results=auth(dom),
                    bulk=True, relationship=rel()))


def l_hr_payroll(n):
    for i in range(n):
        body = p(["Payroll runs on the 25th this month due to the holiday.", "Your 2026 W-2 will be available in the payroll portal in January.",
                  "Benefits open enrollment closes Friday - update your elections in the HR portal."])
        add("Legitimate", "HR / payroll notice", "XL11", "medium", "Genuine HR notice using the company's own portal.", "known internal sender",
            payload(f"HR <hr@{ORG}>", p(["Payroll date", "W-2 availability", "Open enrollment"]), html(body, links=[("HR portal", f"https://hr.{ORG}")]),
                    auth_results=auth(ORG), relationship=rel(sent=3)))


def l_external_firsts(n):
    for i in range(n):
        frm, dom = p([("Maria Gomez <maria@labsourcing.example>", "labsourcing.example"), ("Ken Ito <ken.ito@biostat-consult.example>", "biostat-consult.example"),
                      ("Program Office <grants@research-fund.example>", "research-fund.example")])
        body = p(["We supply validated reagents - happy to send a catalog if useful.", "I'm a biostatistics consultant; would a short call help your trial design?",
                  "Your grant application was received. Decisions are announced in March."])
        add("Legitimate", "external first contact (benign)", "XL12", "medium", "Benign unsolicited or first-contact email.", "unfamiliar sender",
            payload(frm, p(["Hello", "Intro", "Application received"]), html(body), auth_results=auth(dom), relationship=rel()))


PLAN = [(m_callback, 8), (m_legal, 8), (m_onboarding, 8), (m_audit, 8), (m_board, 6), (m_agent, 8), (m_tax_refund, 8), (m_job_check, 8),
        (m_charity, 6), (m_calendar, 8), (m_refund_support, 8), (m_vendor_hijack, 8), (m_sms_pivot, 8),
        (l_audit, 8), (l_procurement, 8), (l_courier, 8), (l_it_rollout, 8), (l_approvals, 10), (l_charity_internal, 6), (l_partner_work, 10),
        (l_exec, 8), (l_security_notes, 8), (l_newsletters, 10), (l_hr_payroll, 8), (l_external_firsts, 8)]

if __name__ == "__main__":
    for fn, k in PLAN:
        fn(k)
    cases = v1.CASES
    for i, c in enumerate(cases, 1):
        c["id"] = f"X{i:03d}"
    labs = [c["label"] for c in cases]
    assert labs.count("Malicious") == 100 and labs.count("Legitimate") == 100, (labs.count("Malicious"), labs.count("Legitimate"))
    with OUT.open("w") as fh:
        for c in cases:
            fh.write(json.dumps({k: c[k] for k in ("id", "label", "category", "family", "difficulty", "rationale", "context", "input")}) + "\n")
    print(f"wrote {len(cases)} cases to {OUT}")
