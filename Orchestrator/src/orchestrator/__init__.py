"""NEXUS-X incident orchestrator."""

__all__ = ["build_workflow"]


def build_workflow(*args, **kwargs):
    from .workflow import build_workflow as _build_workflow

    return _build_workflow(*args, **kwargs)
