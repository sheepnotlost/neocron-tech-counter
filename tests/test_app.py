"""App-level behaviour that does not need the game: closing mid-scan, hotkeys taken."""
import threading
import time

from ntc.app import App
from ntc.lists import ListStore


def make_app(tmp_path):
    return App(ListStore(tmp_path / "lists.json"))


def test_closing_during_a_scan_stops_it_first(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    stopped = threading.Event()

    def slow_scan(target, progress, items=None):            # stands in for a long scan that honours abort
        for _ in range(200):
            if app.scanner.abort_event.is_set():
                stopped.set()
                return []
            time.sleep(0.05)
        return []

    monkeypatch.setattr(app.scanner, "scan", slow_scan)
    app.start_scan()
    time.sleep(0.2)
    t = time.time()
    app.close()
    assert stopped.is_set() and not app.scan_thread.is_alive()
    assert time.time() - t < 3


def test_user_is_told_when_the_hotkeys_are_taken(tmp_path):
    app = make_app(tmp_path)
    app.hotkeys.failed = ["ctrl+alt+s"]
    app._check_hotkeys()
    assert "taken" in app.status.get() and "Scan button" in app.status.get()
    app.close()


class _Ev:
    def __init__(self, x, y):
        self.x_root, self.y_root = x, y


def test_custom_frame_keeps_size_and_respects_minimum(tmp_path):
    app = make_app(tmp_path)
    app.root.update()
    f = app.frame
    assert f is not None and app.body is f.body
    assert (app.root.winfo_width(), app.root.winfo_height()) == (560, 700)      # no stray width from the old frame
    f._start_resize(_Ev(0, 0), "se")
    f._resize(_Ev(-900, -900))
    app.root.update()
    assert (app.root.winfo_width(), app.root.winfo_height()) == f.minsize
    f._start_resize(_Ev(0, 0), "se")
    f._resize(_Ev(40, 30))
    app.root.update()
    assert app.root.winfo_width() == f.minsize[0] + 40
    app.close()


def test_title_bar_buttons_minimise_and_close(tmp_path):
    app = make_app(tmp_path)
    app.root.update()
    app.frame._minimize()
    app.root.update()
    assert app.root.state() == "iconic"
    app.root.deiconify()
    app.frame._close()                        # same path as the native close: stops the scan, frees the hotkeys
    assert app.closing


def test_every_button_label_is_fully_visible(tmp_path):
    """The widest label ('Add manual entry') must fit in its button at the default window size."""
    from tkinter import ttk
    app = make_app(tmp_path)
    app.root.update()

    def buttons(w):
        for c in w.winfo_children():
            if isinstance(c, ttk.Button):
                yield c
            yield from buttons(c)
    for b in buttons(app.body):
        assert b.winfo_width() >= b.winfo_reqwidth() - 1, b.cget("text")
    app.close()
