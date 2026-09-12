"""Entry point for the ``finlang-ui`` script (SOL-112 Phase 0).

Starts the existing FastAPI app on loopback and opens the Workbench in the
default browser. Hyphenated name follows the house convention
(``finlang-discover``, ``finlang-api``); the spec's ``finlang ui`` spelling
was adjusted to match at Phase 0.

The host is hard-pinned to 127.0.0.1 with no override, deliberately (SOL-112
P2): a hosted upload surface would falsify the "runs on your machine" register
the product is sold on. Anyone who genuinely wants network exposure has
``finlang-api`` and owns that decision explicitly.
"""
import os
import threading
import webbrowser


def run() -> None:
    try:
        import uvicorn
    except ImportError:
        # Base deps include the server since the Workbench shipped, so this
        # only fires on an older/partial environment. Guidance beats a
        # traceback either way.
        raise SystemExit(
            "finlang-ui needs the bundled web server, which this environment "
            "is missing.\nFix: pip install -U finlang"
        )

    port = int(os.environ.get("FINLANG_UI_PORT", "8484"))
    url = f"http://127.0.0.1:{port}/ui/"

    # Open the browser once the server has had a moment to bind. A timer beats
    # polling: if the port is taken, uvicorn's own error is the diagnostic and
    # a browser tab showing a connection error is honest about what happened.
    threading.Timer(1.2, webbrowser.open, args=(url,)).start()
    print(f"FinLang Workbench: {url}")

    uvicorn.run(
        "finlang.api.main:app",
        host="127.0.0.1",          # pinned; see module docstring
        port=port,
        log_level=os.environ.get("FINLANG_API_LOG_LEVEL", "warning"),
    )


if __name__ == "__main__":
    run()
