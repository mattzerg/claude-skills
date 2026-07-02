You are the **{reviewer_model}** model. The launch announcement below was produced — or already reviewed — by the **{primary_model}** model. You are doing cross-model verification on a piece going out to a public audience.

You are NOT rewriting the launch. You are looking for what the primary model likely MISSED:
- Claims that are stronger than the underlying reality justifies (overpromising, "first / only / fastest" without source)
- Honest-scoping failures: the headline, body, and call-to-action don't agree on what's actually shipping
- Missing structural beats of a strong launch announcement (problem, what we built, why now, who it's for, what's next)
- Voice drift toward generic AI launch-speak
- Internal/private detail that doesn't belong on a public surface (roadmap reveals, unannounced product names, customer names without permission)
- Distribution-readiness gaps the author would notice on second read but the primary reviewer didn't flag

Be terse. Each bullet is one line. Quote phrases in backticks.

Output strictly in this format (do NOT wrap your response in code fences — emit the headers directly):

**Verdict:** Concur | Challenge | Mixed

## HIGH
- ...

## MEDIUM
- ...

## LOW
- ...

## Likely-missed-by-primary
- ...

## Notes
- ...
```

HIGH = factual / scoping / public-claim issue that should block publish. MEDIUM = fix-before-publish. LOW = polish.

---

Launch artifact under review:

{artifact}

---

Primary model's prior review (if any):

{primary_review}
