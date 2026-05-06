"""Brand anchors prepended to every AI image prompt to keep visuals on-brand."""

# Reference heroes that new generations should look at-home next to.
REFERENCE_HEROES = [
    "build-now-hero.png",
    "alphaevolve-hero.png",
    "business-velocity-hero.png",
    "the-bootstrapping-loop.png",
]

BRAND_ANCHOR = """Aesthetic: dark cosmic / deep navy background; electric blue and warm amber accents; \
minimalist; futuristic; abstract conceptual art (NOT photorealistic). Clean composition, \
high contrast, suitable as a tech blog hero image. NO text, NO letters, NO embedded code, NO logos, \
NO stock-photo people, NO isometric office illustrations, NO cartoon mascots. Looks like a \
Zerg AI research blog hero (similar to Anthropic / OpenAI research blog aesthetic but darker)."""

ASPECT_HINTS = {
    "1.91:1": "Wide hero composition. Center the focal element with aura/glow extending into the wide frame. "
              "Keep load-bearing visual elements in the center 80% (platform crop tolerance).",
    "16:9":   "Horizontal flow composition. Can use left-to-right narrative or before/after split.",
    "1:1":    "Square LinkedIn-feed composition. Center single focal element OR vertically stacked elements. "
              "Higher visual density than landscape — works because the frame is taller.",
    "3:2":    "Diagram-friendly aspect. Slightly taller than 16:9, gives breathing room for hierarchy diagrams.",
}


def wrap_prompt(concept: str, aspect: str = "1.91:1") -> str:
    """Wrap a concept prompt with brand anchor + aspect-specific composition hint."""
    aspect_hint = ASPECT_HINTS.get(aspect, "")
    return f"{concept}\n\n{BRAND_ANCHOR}\n\n{aspect_hint}".strip()
