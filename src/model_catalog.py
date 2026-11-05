"""Read region-specific, hosted Cohere chat availability from OCI model discovery."""

from datetime import datetime, timezone


def available_chat_model_ids(items, region: str) -> list[str]:
    now = datetime.now(timezone.utc)
    names = set()
    for item in items:
        model_id = getattr(item, "model_id", "") or ""
        if not model_id.lower().startswith("cohere."):
            continue
        if getattr(item, "model_access", None) != "HOSTED":
            continue
        if "CHAT" not in (getattr(item, "capabilities", None) or []):
            continue
        for availability in getattr(item, "availability", None) or []:
            if availability.region != region:
                continue
            if "ON_DEMAND" not in (availability.serving_modes or []):
                continue
            retired = getattr(availability, "time_on_demand_retired", None)
            if retired is not None:
                if retired.tzinfo is None:
                    retired = retired.replace(tzinfo=timezone.utc)
                if retired <= now:
                    continue
            names.add(model_id)
    return sorted(names)
