/**
 * Developer-only text-direction test (Phase 2 research). CardService has no dir/alignment
 * control, so the only tools are Unicode bidi control characters. This card renders the
 * same English sample in each variant, in every text slot the design uses, so the owner can
 * check which one reads correctly in RTL (Hebrew) Gmail. Not reachable in production builds.
 */

var BIDI_SAMPLE = 'Replies go to a different address. 1. Verify by phone (75/100) billing@acmesupply.example';

var BIDI_VARIANTS = [
  { id: 'A', name: 'plain (no control characters)', wrap: function (s) { return s; } },
  { id: 'B', name: 'LRM at start and end (U+200E)', wrap: function (s) { return '\u200E' + s + '\u200E'; } },
  { id: 'C', name: 'LRI ... PDI isolate (U+2066/2069)', wrap: function (s) { return '\u2066' + s + '\u2069'; } },
  { id: 'D', name: 'LRE ... PDF embedding (U+202A/202C)', wrap: function (s) { return '\u202A' + s + '\u202C'; } }
];

function onBidiTest() {
  if (!isDevBuild_()) return notify_('Developer tools are not available in this build.');
  var card = CardService.newCardBuilder().setHeader(CardService.newCardHeader().setTitle('Text direction test (dev)'));
  card.addSection(CardService.newCardSection().addWidget(CardService.newTextParagraph().setText(
    'Each variant shows the same sample in a paragraph, a decorated row (bold title, text, labels) and a ' +
    'score bar. Correct result: the period follows "address", "1." starts "Verify", and the address and ' +
    '"(75/100)" read left to right.')));
  BIDI_VARIANTS.forEach(function (v) {
    var w = v.wrap;
    card.addSection(CardService.newCardSection().setHeader('Variant ' + v.id + ': ' + v.name)
      .addWidget(CardService.newTextParagraph().setText(w(escapeHtml_(BIDI_SAMPLE))))
      .addWidget(withIcon_(CardService.newDecoratedText()
        .setTopLabel(w('Observed in this email. 1 of 2'))
        .setText(w('<b>Unusual reply address</b>') + '<br>' + w(escapeHtml_(BIDI_SAMPLE)))
        .setBottomLabel(w('billing@acmesupply.example (75/100).'))
        .setWrapText(true), 'alternate_email'))
      .addWidget(CardService.newTextParagraph().setText(
        '<font color="#d93025"><b>' + w('High risk · 75/100') + '</b></font><br>' + w('▰▰▰▰▰▰▰▰▱▱'))));
  });
  return CardService.newActionResponseBuilder().setNavigation(CardService.newNavigation().pushCard(card.build())).build();
}
