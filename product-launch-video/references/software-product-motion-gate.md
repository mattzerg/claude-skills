# Software Product Motion Gate

Use this gate before rendering or showing a software product video, especially when the first draft could become a literal screen recording.

## Required Choice

Pick one production mode explicitly:

- **Designed UI motion**: recreated UI components, staged states, animated cards/panels/cursors, proof-backed but not raw capture.
- **Polished live capture**: real app recording with planned crops, zooms, overlays, and edit beats.
- **Hybrid**: live capture for proof moments, designed UI motion for setup, transitions, and explanation.

If the user allows stylization, prefer designed UI motion for launch clips unless the claim depends on a live-only event.

## Truth Policy

- It is acceptable to fake layout, timing, crops, simplified UI, and staged surrounding cards.
- It is not acceptable to fake the core product claim, customer proof, pricing, permissions, audit trails, or performance.
- Mark any staged UI as stylized/source-backed in the production notes.
- Keep a short proof note tying the staged moment to verified product behavior or source footage.

## Keyframe Gate

Do not render until these frames are described:

1. First frame / paused thumbnail.
2. Hook frame where the viewer understands the category.
3. Proof setup frame with the important UI state visible.
4. Product transformation frame.
5. Proof hold frame after the state change.
6. End card.

Each keyframe must specify crop, focal element, on-screen copy, motion, and what claim it supports.

## Software Video Quality Bar

- UI fills the frame; avoid tiny full-browser views.
- No browser chrome unless browser chrome is the product.
- Captions are short and tied to visible state changes.
- One mechanic per short clip.
- Camera motion has a reason: reveal, focus, proof, or transition.
- Cursor motion is either meaningful or absent.
- First frame works as a thumbnail.
- Product proof appears in the first third of the runtime.
- End card has product name, concrete CTA, and readable hold.

## Failure Modes

- Treating a proof recording as a launch video.
- Huge captions covering the UI event.
- Full-board shots where no card, command, or state change is readable.
- Explaining abstract value while the screen shows generic UI.
- Showing every feature instead of one believable transformation.
