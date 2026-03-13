"""Frontend package — 静态资源定位与加载。"""

from __future__ import annotations

import json
from functools import lru_cache
from html import escape
from pathlib import Path

from ..backend.demo_repo import PARALLEL_CALCULUS_PROMPT

_DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"

_DASHBOARD_ASSETS = {
    "style.css": "text/css; charset=utf-8",
    "app.js": "application/javascript; charset=utf-8",
}

_TRACE_VIEWER_DIR = Path(__file__).resolve().parent / "trace_viewer"


def render_dashboard_html(initial_run_id: str | None) -> str:
    selected = initial_run_id or ""
    return (
        _load_dashboard_template()
        .replace("__INITIAL_PROMPT__", escape(PARALLEL_CALCULUS_PROMPT))
        .replace("__SELECTED_JSON__", json.dumps(selected))
        .replace("__SELECTED_LABEL__", escape(selected))
    )


def read_dashboard_asset(asset_name: str) -> tuple[str, str]:
    content_type = _DASHBOARD_ASSETS.get(asset_name)
    if content_type is None:
        raise FileNotFoundError(asset_name)
    return _load_text_asset(asset_name), content_type


def load_trace_viewer_template() -> str:
    return (_TRACE_VIEWER_DIR / "index.html").read_text(encoding="utf-8")


def load_trace_viewer_css() -> str:
    return (_TRACE_VIEWER_DIR / "style.css").read_text(encoding="utf-8")


def load_trace_viewer_js() -> str:
    return (_TRACE_VIEWER_DIR / "app.js").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _load_dashboard_template() -> str:
    return (_DASHBOARD_DIR / "index.html").read_text(encoding="utf-8")


@lru_cache(maxsize=len(_DASHBOARD_ASSETS))
def _load_text_asset(asset_name: str) -> str:
    return (_DASHBOARD_DIR / asset_name).read_text(encoding="utf-8")
