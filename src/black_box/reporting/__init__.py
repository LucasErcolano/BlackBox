"""Black Box reporting module — PDF generation and diff utilities."""
from .diff import scoped_check, side_by_side_html, unified_diff_str
from .pdf_report import build_report

__all__ = [
    "build_report",
    "unified_diff_str",
    "scoped_check",
    "side_by_side_html",
]
