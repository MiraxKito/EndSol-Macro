"""Input guard for the dry-run mode.

Every click and key press the macro sends to the game goes through this
module. With the dry-run mode on nothing is sent — the macro only writes down
what it would have done. Without this guard the dry-run mode would only
cover the handful of places that remembered to check it, and the macro would
still click, craft and buy things in the game.

The tracker sets the flag when the config is loaded or saved and installs a
sink for the log lines.
"""

import autoit as _autoit
import pyautogui as _pyautogui

_dry = False
_log_sink = None
_counts = {}


def set_dry_run(active: bool) -> None:
    """Turn the dry-run mode on or off for every input call."""
    global _dry
    _dry = bool(active)


def is_dry_run() -> bool:
    return _dry


def set_log_sink(callback) -> None:
    """Install the function that writes the dry-run lines into the macro log."""
    global _log_sink
    _log_sink = callback


def _note(action: str) -> None:
    """Count the blocked calls and write the interesting ones into the log."""
    _counts[action] = _counts.get(action, 0) + 1
    count = _counts[action]
    if count != 1 and count % 50 != 0:
        return
    if _log_sink is None:
        return
    try:
        _log_sink(f"{action} (blocked {count}x)")
    except Exception:
        pass


class _AutoIt:
    """autoit with the dry-run guard in front of the input functions."""

    def send(self, *args, **kwargs):
        if _dry:
            _note(f"type {args[0] if args else ''}".strip())
            return
        return _autoit.send(*args, **kwargs)

    def key_down(self, *args, **kwargs):
        if _dry:
            _note(f"press {args[0] if args else ''}".strip())
            return
        return _autoit.key_down(*args, **kwargs)

    def key_up(self, *args, **kwargs):
        if _dry:
            _note(f"release {args[0] if args else ''}".strip())
            return
        return _autoit.key_up(*args, **kwargs)

    def mouse_click(self, *args, **kwargs):
        if _dry:
            _note("click")
            return
        return _autoit.mouse_click(*args, **kwargs)

    def mouse_move(self, *args, **kwargs):
        if _dry:
            _note("move the mouse")
            return
        return _autoit.mouse_move(*args, **kwargs)

    def mouse_down(self, *args, **kwargs):
        if _dry:
            _note("press the mouse button")
            return
        return _autoit.mouse_down(*args, **kwargs)

    def mouse_up(self, *args, **kwargs):
        if _dry:
            _note("release the mouse button")
            return
        return _autoit.mouse_up(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(_autoit, name)


class _PyAutoGui:
    """pyautogui with the dry-run guard in front of the input functions."""

    def click(self, *args, **kwargs):
        if _dry:
            _note("click")
            return
        return _pyautogui.click(*args, **kwargs)

    def moveTo(self, *args, **kwargs):
        if _dry:
            _note("move the mouse")
            return
        return _pyautogui.moveTo(*args, **kwargs)

    def press(self, *args, **kwargs):
        if _dry:
            _note(f"press {args[0] if args else ''}".strip())
            return
        return _pyautogui.press(*args, **kwargs)

    def keyDown(self, *args, **kwargs):
        if _dry:
            _note(f"press {args[0] if args else ''}".strip())
            return
        return _pyautogui.keyDown(*args, **kwargs)

    def keyUp(self, *args, **kwargs):
        if _dry:
            _note(f"release {args[0] if args else ''}".strip())
            return
        return _pyautogui.keyUp(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(_pyautogui, name)


autoit = _AutoIt()
pyautogui = _PyAutoGui()
