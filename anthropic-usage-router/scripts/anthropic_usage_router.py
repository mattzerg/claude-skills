#!/usr/bin/env python3
"""Deprecated API-key router shim.

Claude routing should use account-based Claude.ai OAuth through zclaude. This
script intentionally fails closed so stale automation cannot resurrect
ANTHROPIC_API_KEY routing.
"""
from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    del argv
    sys.stderr.write(
        "anthropic-usage-router is disabled. Use account-based Claude.ai "
        "routing instead:\n"
        "  ~/.config/zerg/zclaude router-status\n"
        "  ~/.config/zerg/zclaude router-route\n"
        "  ~/.config/zerg/zclaude max-use <label>\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
