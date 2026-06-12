"""Local project/client priority rules.

The canonical project registry remains the source of project metadata. This
module overlays operator-local priority rules from ``temp/rbos.config`` so
personal/client value preferences can affect dashboards without committing
client names into the repo.
"""

from __future__ import annotations

from typing import Any

from rebalance.ingest.config import get_project_priority_rules
from rebalance.ingest.project_classifier import normalize_match_text

# Phase 5: one normalizer across classifier/inference/priority — the
# canonical implementation lives in project_classifier. Name kept for
# this module's existing call sites.
normalize_priority_text = normalize_match_text


def _project_aliases(project: dict[str, Any]) -> set[str]:
    aliases = {normalize_priority_text(str(project.get("name") or ""))}
    custom_fields = project.get("custom_fields") or {}
    if isinstance(custom_fields, dict):
        for key in ("aliases", "calendar_aliases", "calendar_keywords", "keywords"):
            value = custom_fields.get(key)
            if isinstance(value, list):
                aliases.update(normalize_priority_text(str(item)) for item in value)
            elif isinstance(value, str):
                aliases.add(normalize_priority_text(value))
    return {alias for alias in aliases if alias}


def _rule_aliases(rule: dict[str, Any]) -> set[str]:
    aliases = {normalize_priority_text(str(rule.get("name") or ""))}
    for alias in rule.get("aliases") or []:
        aliases.add(normalize_priority_text(str(alias)))
    return {alias for alias in aliases if alias}


def _matches(project: dict[str, Any], rule: dict[str, Any]) -> bool:
    return bool(_project_aliases(project) & _rule_aliases(rule))


def priority_score(project: dict[str, Any]) -> int:
    """Return a stable score where higher means more important to surface."""
    custom_fields = project.get("custom_fields") or {}
    tier = project.get("priority_tier")
    try:
        tier_int = int(tier) if tier is not None else 99
    except (TypeError, ValueError):
        tier_int = 99
    tier_points = max(0, 6 - tier_int) * 100

    raw_value_score = custom_fields.get("value_score")
    try:
        value_points = int(raw_value_score or 0) * 5
    except (TypeError, ValueError):
        value_points = 0

    risk_level = str(project.get("risk_level") or "").casefold()
    risk_points = {"high": 20, "medium": 10, "low": 0}.get(risk_level, 0)
    return tier_points + value_points + risk_points


def apply_project_priorities(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Overlay local priority rules and add virtual rows for unmatched rules."""
    rules = get_project_priority_rules()
    if not rules:
        return [dict(project) for project in projects]

    out = [dict(project) for project in projects]
    matched_rule_names: set[str] = set()

    for index, project in enumerate(out):
        merged = dict(project)
        custom_fields = dict(merged.get("custom_fields") or {})
        for rule in rules:
            if not _matches(merged, rule):
                continue
            matched_rule_names.add(rule["name"].casefold())
            if rule.get("priority_tier") is not None:
                merged["priority_tier"] = rule["priority_tier"]
            if rule.get("value_level"):
                merged["value_level"] = rule["value_level"]
            if rule.get("risk_level"):
                merged["risk_level"] = rule["risk_level"]
            if rule.get("client"):
                custom_fields["client"] = rule["client"]
            if rule.get("value_score") is not None:
                custom_fields["value_score"] = rule["value_score"]
            if normalize_priority_text(str(merged.get("name") or "")) != normalize_priority_text(rule["name"]):
                custom_fields["priority_display_name"] = rule["name"]
            custom_fields["priority_source"] = "local_config"
            rule_aliases = list(rule.get("aliases") or [])
            if rule_aliases:
                existing_aliases = list(custom_fields.get("aliases") or [])
                for alias in rule_aliases:
                    if alias not in existing_aliases:
                        existing_aliases.append(alias)
                custom_fields["aliases"] = existing_aliases
        merged["custom_fields"] = custom_fields
        merged["priority_score"] = priority_score(merged)
        out[index] = merged

    for rule in rules:
        if rule["name"].casefold() in matched_rule_names:
            continue
        custom_fields = {
            "aliases": list(rule.get("aliases") or []),
            "priority_source": "local_config",
        }
        if rule.get("client"):
            custom_fields["client"] = rule["client"]
        if rule.get("value_score") is not None:
            custom_fields["value_score"] = rule["value_score"]
        project = {
            "name": rule["name"],
            "status": "active",
            "summary": "",
            "value_level": rule.get("value_level"),
            "priority_tier": rule.get("priority_tier"),
            "risk_level": rule.get("risk_level"),
            "repos": [],
            "tags": ["priority-seed"],
            "custom_fields": custom_fields,
        }
        project["priority_score"] = priority_score(project)
        out.append(project)

    return out
