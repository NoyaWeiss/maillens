/**
 * Developer-only render bisection (Phase 2). Gmail rejects invalid cards on the client, after our
 * code returns, so the only way to find which construct it rejects is to render each one alone.
 * Each button pushes a small card that differs from a known-good baseline in exactly one way.
 * Reachable from the Backend settings card (universal action) in dev builds only.
 */

var RENDER_TESTS = [
  { id: 'A', name: 'Baseline (v1-style, known good)' },
  { id: 'B', name: 'No card header' },
  { id: 'C', name: 'Tonal + borderless buttons' },
  { id: 'D', name: 'Row with icon only (no labels)' },
  { id: 'E', name: 'Isolates in section header and button text' },
  { id: 'F', name: 'Full v3 main card (sample High)' }
];

function renderTestSection_() {
  var s = CardService.newCardSection().setHeader('Render tests (dev)');
  RENDER_TESTS.forEach(function (t) {
    s.addWidget(CardService.newTextButton().setText(t.id + ': ' + t.name)
      .setOnClickAction(CardService.newAction().setFunctionName('onRenderTest').setParameters({ v: t.id })));
  });
  return s;
}

function onRenderTest(e) {
  if (!isDevBuild_()) return notify_('Developer tools are not available in this build.');
  var v = e.parameters.v;
  var card = v === 'F' ? sampleV3Card_() : renderVariant_(v);
  return CardService.newActionResponseBuilder().setNavigation(CardService.newNavigation().pushCard(card)).build();
}

function renderVariant_(v) {
  var b = CardService.newCardBuilder();
  if (v !== 'B') b.setHeader(CardService.newCardHeader().setTitle('Render test ' + v));
  var s = CardService.newCardSection();
  if (v === 'E') s.setHeader('⁦Section header with isolate⁩');
  s.addWidget(CardService.newTextParagraph().setText('<b>Variant ' + v + '</b>: if you can read this, it rendered.'));
  var row = CardService.newDecoratedText().setText('<b>Row title</b><br>Row explanation.').setWrapText(true);
  if (v !== 'D') row.setTopLabel('Top label');
  s.addWidget(withIcon_(row, 'info', 'Row'));
  var primary = CardService.newTextButton().setText(v === 'E' ? '⁦View detailed analysis⁩' : 'Primary')
    .setOnClickAction(CardService.newAction().setFunctionName('onRenderTest').setParameters({ v: 'A' }));
  var secondary = CardService.newTextButton().setText(v === 'E' ? '⁦Re-analyze⁩' : 'Secondary')
    .setOnClickAction(CardService.newAction().setFunctionName('onRenderTest').setParameters({ v: 'A' }));
  if (v === 'C') {
    primary.setTextButtonStyle(CardService.TextButtonStyle.FILLED_TONAL);
    secondary.setTextButtonStyle(CardService.TextButtonStyle.BORDERLESS);
  } else {
    primary.setTextButtonStyle(CardService.TextButtonStyle.OUTLINED);
    secondary.setTextButtonStyle(CardService.TextButtonStyle.OUTLINED);
  }
  s.addWidget(CardService.newButtonSet().addButton(primary).addButton(secondary));
  return b.addSection(s).build();
}

/** The real v3 renderer with a fixed High-risk sample (same shape as the backend response). */
function sampleV3Card_() {
  return buildResultCard_({
    request_id: 'rendertest', verdict: 'HIGH', score: 75, headline: 'A reply in a vendor thread asks you to send money to new bank details.',
    category: 'Possible vendor impersonation', impact: 'Payment could be redirected to an attacker-controlled account and may be difficult to recover.',
    reasons: [{ title: 'Reply address changed', summary: 'Replies now go to a different address than earlier messages in this thread.', basis: 'Seen in this email' },
      { title: 'Asks to change bank details', summary: 'It asks you to pay a new account.', basis: 'Based on the wording' }],
    actions: [{ title: 'Verify with the vendor', detail: 'Call a number you already trust before changing any payment details.' },
      { title: "Don't reply to this email", detail: 'Replies may reach the attacker.' }],
    findings: [], also_observed: [], suppressed: [], story: [], checks: [], out_of_scope: [], assumptions: [], pressure_cues: []
  }, 'rendertest', ['gmail.readonly']);
}
