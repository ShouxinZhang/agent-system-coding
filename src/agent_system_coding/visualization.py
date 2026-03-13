"""Visualization — 兼容转发层。

原有的公共 API 已迁移到 backend.snapshot 和 backend.writers，
此文件保留向后兼容，避免外部 import 断裂。
"""

from .backend.snapshot import load_runtime_snapshot  # noqa: F401
from .backend.writers import (  # noqa: F401
    render_trace_viewer_html,
    write_graph_mermaid,
    write_latest_status,
    write_trace_report,
    write_trace_viewer_html,
)
