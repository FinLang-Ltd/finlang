"""FinLang Workbench — the local UI package (SOL-112).

Static assets live in ``static/`` and are served by the existing FastAPI app
via a guarded mount in ``finlang.api.main``. This package deliberately contains
no engine logic of any kind: the UI is a consumer of the API, and the API
shells to the CLI. One engine (SOL-112 P1).
"""
