"""Compatibility shim for the old client FastFlags helper.

The macro never applied client FastFlags itself — the launchers (Bloxstrap /
Fishstrap) apply them when they start the client, so nothing in the project
imports this module. The old re-export pointed at a `base_support` function
that no longer exists, which made `import biome_tracker.fastflags` fail with
an ImportError. The module is kept (and made importable) so an external
import does not break.
"""


def apply_fast_flags(flags=None) -> bool:
    """Client FastFlags are handled by the launcher, not by the macro.

    Kept for backwards compatibility with callers that still import this
    name. Returns False because there is nothing for the macro to apply.
    """
    return False


__all__ = ["apply_fast_flags"]
