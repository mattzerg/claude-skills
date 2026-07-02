# Mockup Quality Gate

Use this gate before showing any swag review PDF.

## Automatic Checks

Run:

```bash
python3 <skill>/scripts/mockup_preflight.py <mockup-folder>
```

Fix all HIGH findings before presenting. Use `--strict` when preparing vendor-facing work.

The script catches:

- Elements and text that bleed off the SVG artboard.
- Review labels too close to the page edge.
- Full wordmark inside the same terminal/campaign group as the hero command.
- Rotated full wordmarks that are likely fake object placement.
- Oversized T-shirt chest graphics that read as pasted panels rather than real screen prints.
- Full wordmarks placed in shirt sleeve/armpit danger zones or as oversized lower-hem blocks.
- T-shirt full-logo tags placed so low they crop out of the contact sheet or read as floating labels.
- Mug full wordmarks pushed into the handle/crop danger zone instead of a coherent front stack or separate side-view mockup.
- Hoodie files that lack hoodie-specific anatomy markers.
- Mug files that lack handle-side placement language.
- Excess repeated full wordmarks in one mockup.

## Visual Checks

After rendering PNG previews, inspect the contact sheet and one-up item pages. Do not rely on source validation alone.

Block and revise if:

- A logo bleeds off a garment, mug, card, or page.
- A hoodie silhouette reads as a T-shirt, sweatshirt, or generic torso.
- Any label or explanatory text is hidden behind the mockup.
- The full logo looks like a pasted sponsor logo rather than a real placement.
- Apparel marks respect printable zones: center chest, tagless neck, real sleeve plane, small hem tag, or back yoke.
- The campaign graphic and full wordmark compete for the same visual role.
- The item does not communicate where the logo would physically be produced.

## Required Fix Behavior

When a HIGH issue is found, fix it automatically if the intent is clear:

- Move full wordmarks out of hero panels and into secondary item zones.
- Shorten or reposition explanatory labels that clip.
- Replace a weak silhouette with a more accurate object anatomy.
- Reduce duplicated logos before adding more decoration.

Only ask the user when the needed item or brand decision is genuinely ambiguous.
