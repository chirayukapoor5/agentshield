"""Minimal AgentShield MCP compatibility layer.

This is a safe, local compatibility layer for tool exposure. In production, switch
this to the maintained official MCP SDK and remote transport with explicit auth.
"""

from __future__ import annotations

from typing import Any


def list_authorized_websites() -> list[dict[str, Any]]:
    return [{"name": "demo website", "status": "approved", "url": "https://example.com"}]


def get_compatibility_report(website_id: int) -> dict[str, Any]:
    return {"website_id": website_id, "compatibility_score": 92, "status": "ok"}


def get_security_findings(website_id: int) -> list[dict[str, Any]]:
    return [{"website_id": website_id, "severity": "medium", "title": "Review document trust boundaries."}]


def search_agent_activity(query: str) -> list[dict[str, Any]]:
    return [{"query": query, "matching_events": 1, "status": "ok"}]


def get_policy_status() -> dict[str, Any]:
    return {"mode": "dry_run", "active_policies": 2, "status": "ok"}


def generate_report(website_id: int) -> dict[str, Any]:
    return {"website_id": website_id, "format": "json", "status": "generated"}
