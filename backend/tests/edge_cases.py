"""Phase 3 edge-case suite, written before running the engine on it.

kind: "negative" = legitimate mail that must stay LOW (or INCONCLUSIVE only where auth is missing),
      "known_fp" = documented false positive, pinned so any behaviour change is noticed,
      "attack"   = must reach at least the expected verdict,
      "known_fn" = documented blind spot (spec section 10): asserted to stay LOW so a change is noticed.
"""

from tests.factory import PASS

REL = {"known_domains": ["northwind.example", "acmesupply.example", "corp.example"], "sender_sent_count": 0,
       "name_match_addresses": []}
KNOWN = lambda addr: {**REL, "sender_sent_count": 3, "name_match_addresses": []}

CASES = [
    # ---------------------------------------------------------------- hard negatives
    ("contractor_personal_gmail", "negative", "LOW", dict(
        from_header="Maya Levi <maya.levi.design@gmail.com>", relationship=REL,
        html='<p>Hi! Could you review the draft before Thursday? '
             '<a href="https://docs.google.com/document/d/abc">Draft v2</a></p><p>Thanks, Maya</p>')),
    ("password_reset_service", "negative", "LOW", dict(
        from_header="CloudMail <no-reply@accounts.cloudmail.example>", relationship=REL,
        html='<p>We received a request to reset your password. '
             '<a href="https://accounts.cloudmail.example/reset?t=1">Reset password</a>. '
             "If you didn't request this, ignore this email.</p>")),
    ("verification_code_delivery", "negative", "LOW", dict(
        from_header="Bank <alerts@northwindbank.example>", relationship=REL,
        html="<p>Your verification code is 482913. Never share this code with anyone, including us.</p>")),
    ("calendar_invite", "negative", "LOW", dict(
        from_header="Google Calendar <calendar-notification@google.com>", relationship=REL,
        subject="Invitation: Q4 sync @ Tue 10am",
        html='<p>Dana Cohen has invited you. <a href="https://calendar.google.com/event?eid=x">More options</a></p>')),
    ("mailing_list_reply_to", "negative", "LOW", dict(
        from_header="Dana Cohen <dana.cohen@northwind.example>", relationship=KNOWN("dana.cohen@northwind.example"),
        reply_to="eng-team@lists.northwind.example", bulk=True,
        html="<p>Notes from today's architecture review are attached.</p>")),
    ("helpdesk_ticket_reply", "negative", "LOW", dict(
        from_header="Acme Support <support@acmesupply.example>", relationship=REL,
        reply_to="support@acmesupply.zendesk.example", subject="Re: [Ticket 4821] Printer toner",
        in_reply_to="<t4821@acmesupply.example>",
        html="<p>Your replacement toner shipped today. Reply to this email if anything is missing.</p>")),
    # Was a known false positive (F-16); fixed in Phase 3b by the reported-speech guard (RC5).
    ("security_newsletter_discusses_phishing", "negative", "LOW", dict(
        from_header="Weekly Security <news@secweekly.example>", bulk=True, relationship=REL,
        html="<h2>This week in phishing</h2><p>Scammers increasingly email finance teams claiming their bank "
             "details have changed and asking them to wire payments to a new account. Some even hide text like "
             "'ignore previous instructions' to fool AI filters. Always verify by phone.</p>")),
    ("known_vendor_invoice_pdf", "negative", "LOW", dict(
        from_header="Acme Supply Billing <billing@acmesupply.example>", relationship=KNOWN("billing@acmesupply.example"),
        attachments=[{"name": "INV-2301.pdf", "content_type": "application/pdf", "size": 52000}],
        html="<p>Please find invoice INV-2301 attached, payable to our usual account by Friday.</p>")),
    ("known_name_same_domain_new_address", "negative", "LOW", dict(
        from_header="Dana Cohen <dcohen@northwind.example>",
        relationship={**REL, "name_match_addresses": ["dana.cohen@northwind.example"]},
        html="<p>New address, same me. Let's sync next week.</p>")),
    ("shipping_bulk_shortener", "negative", "LOW", dict(
        from_header="ShipFast <updates@shipfast.example>", bulk=True, relationship=REL,
        html='<p>Your parcel is on its way. Track it: <a href="https://bit.ly/3xYz">https://bit.ly/3xYz</a></p>')),
    ("docusign_via", "negative", "LOW", dict(
        from_header="Dana Cohen via DocuSign <dse@docusign.net>", relationship=REL,
        html='<p>Please review and sign. <a href="https://www.docusign.net/Signing/?ti=1">Review document</a></p>')),
    ("internal_it_portal_announcement", "negative", "LOW", dict(
        from_header="IT Support <it@corp.example>", relationship=REL,
        html='<p>Our new HR portal is live. Please sign in to review your benefits at '
             '<a href="https://portal.corp.example">portal.corp.example</a>.</p>')),
    ("forwarded_no_auth_no_ask", "negative", "LOW", dict(
        from_header="Dana Cohen <dana.cohen@northwind.example>", auth=None, relationship=KNOWN("x"),
        subject="Fwd: lunch menu", html="<p>---------- Forwarded message ----------</p><p>Friday: pasta.</p>")),
    ("legit_paypal_receipt", "negative", "LOW", dict(
        from_header="PayPal <service@paypal.com>", relationship=REL,
        html='<p>You sent $20.00. <a href="https://www.paypal.com/activity">paypal.com/activity</a></p>')),
    ("esp_tracked_link_text", "negative", "LOW", dict(
        from_header="Northwind News <news@northwind.example>", bulk=True, relationship=REL,
        html='<p><a href="https://u123.ct.sendgrid.net/ls/click?upn=x">www.northwind.example/blog</a></p>')),
    ("payslip_notice", "negative", "LOW", dict(
        from_header="Payroll <payroll@corp.example>", relationship=REL,
        html="<p>Your payslip for October is now available in the payroll portal.</p>")),
    ("re_without_in_reply_to", "negative", "LOW", dict(
        from_header="Dana Cohen <dana.cohen@northwind.example>", relationship=KNOWN("x"), subject="Re: budget",
        html="<p>Sounds good, approved.</p>")),

    # ---------------------------------------------------------------- attacks
    ("gift_cards_unfamiliar_urgent", "attack", "HIGH", dict(
        from_header="Robert Hale <robert.hale.office@gmail.com>", relationship=REL,
        html="<p>I need you to buy 5 Apple gift cards urgently for a client today. Keep this between us.</p>")),
    ("ceo_wire_freemail_urgent", "attack", "HIGH", dict(
        from_header="John Smith <john.smith.ceo@gmail.com>", relationship=REL,
        html="<p>Urgent: wire the payment to our new account today. I'm in meetings, don't call. "
             "Our bank details have changed.</p>")),
    ("ip_literal_credential_link", "attack", "HIGH", dict(
        from_header="Mail Admin <admin@mailbox-quota.example>", relationship=REL,
        html='<p>Sign in to verify your account: <a href="http://192.0.2.44/owa/login">Verify</a></p>')),
    ("userinfo_trick", "attack", "HIGH", dict(
        from_header="Bank <alerts@bank-secure.example>", relationship=REL,
        html='<p><a href="https://www.northwindbank.example@evil.example/login">Open statement</a></p>')),
    ("double_extension_exe", "attack", "HIGH", dict(
        from_header="Accounts <ap@vendor-billing.example>", relationship=REL,
        attachments=[{"name": "invoice.pdf.exe", "content_type": "application/octet-stream", "size": 90000}],
        html="<p>Invoice attached.</p>")),
    ("dmarc_reject_fail_credential", "attack", "HIGH", dict(
        from_header="Northwind Bank <alerts@northwindbank.example>", relationship=REL,
        auth="mx.google.com; spf=fail smtp.mailfrom=evil.example; dkim=none; "
             "dmarc=fail (p=REJECT sp=REJECT dis=NONE) header.from=northwindbank.example",
        html="<p>Please sign in to verify your account.</p>")),
    ("corporate_to_freemail_reply_bank_change", "attack", "HIGH", dict(
        from_header="Acme Billing <billing@acmesupply.example>", relationship=KNOWN("x"),
        reply_to="acme.billing.dept@gmail.com",
        html="<p>Our bank details have changed. Please wire the open invoices to our new account.</p>")),
    ("mfa_code_relay", "attack", "SUSPICIOUS", dict(
        from_header="IT Helpdesk <helpdesk@corp-support.example>", relationship=REL,
        html="<p>We are migrating your mailbox. Please reply with the 6-digit code you just received.</p>")),
    ("rn_m_lookalike_brand", "attack", "HIGH", dict(
        from_header="Microsoft 365 <security@rnicrosoft.com>", relationship=REL,
        html="<p>Unusual sign-in activity was detected.</p>")),

    # ---------------------------------------------------------------- documented blind spots (spec section 10)
    ("plain_text_phish_clean_auth", "known_fn", "LOW", dict(
        from_header="Account Team <team@account-review.example>", relationship=REL,
        html="<p>We noticed a problem with your account. Please sign in at our portal to keep it active.</p>")),
    ("qr_code_image_phish", "known_fn", "LOW", dict(
        from_header="HR <hr@benefits-update.example>", relationship=REL,
        html='<p>Scan the code below to update your benefits.</p><img src="cid:qr">')),
]
