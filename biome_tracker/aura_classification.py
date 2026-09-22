"""
Aura classification system for Sol's RNG.

Data-driven approach: classifies auras based on their properties from
the Fandom wiki data (auras_data), not hardcoded names.

Aura types:
  - normal: rollable anywhere, no special conditions
  - biome_native: boosted chance in specific biome(s) — always webhook
  - biome_exclusive: ONLY rollable in specific biome — always webhook
  - breakthrough: obtainable via Breakthrough mechanic — always webhook
  - crafted: made at Jake's Workshop — always webhook
  - potion_required: requires specific potion to roll — always webhook
  - event_exclusive: only during limited events — always webhook
  - limbo: only in Limbo area — always webhook
"""

from __future__ import annotations
from typing import Any


def classify_aura(aura_name: str, aura_info: dict[str, Any]) -> dict[str, Any]:
    """
    Classify an aura based on its wiki data properties.

    Returns dict with:
      - type: the aura type constant
      - always_webhook: whether this aura bypasses rarity threshold
      - condition: human-readable condition description
      - biome: the relevant biome (if applicable)
    """
    result = {
        "type": "normal",
        "always_webhook": False,
        "condition": "",
        "biome": "",
    }

    if not isinstance(aura_info, dict):
        return result

    obtainment = (aura_info.get("obtainment") or "").strip()
    rarity_val = _parse_rarity(aura_info.get("rarity"))
    exclusive_biome_list = aura_info.get("exclusive_biome", [])
    native_biome_list = aura_info.get("native_biome", [])
    rarity_name = (aura_info.get("rarity_name") or "").strip()

    # --- Check for biome-exclusive (only in specific biome) ---
    if isinstance(exclusive_biome_list, list) and len(exclusive_biome_list) >= 1:
        biome = exclusive_biome_list[0] if exclusive_biome_list[0] != "None" else ""
        if biome:
            result["type"] = "biome_exclusive"
            result["always_webhook"] = True
            result["condition"] = f"Only in {biome}"
            result["biome"] = biome
            return result

    # --- Check for biome-native (boosted in specific biome) ---
    if isinstance(native_biome_list, list) and len(native_biome_list) >= 1:
        biome = native_biome_list[0] if native_biome_list[0] != "None" else ""
        if biome:
            multiplier = native_biome_list[1] if len(native_biome_list) > 1 else 1
            result["type"] = "biome_native"
            result["always_webhook"] = False  # Native does NOT bypass threshold
            result["condition"] = f"Native to {biome} (x{multiplier})"
            result["biome"] = biome
            return result

    # --- Check for crafted/shop obtainment ---
    if obtainment:
        obtain_lower = obtainment.lower()
        if any(kw in obtain_lower for kw in ["craft", "workshop", "jake"]):
            result["type"] = "crafted"
            result["always_webhook"] = True
            result["condition"] = f"Crafted: {obtainment}"
            return result
        if "potion" in obtain_lower:
            result["type"] = "potion_required"
            result["always_webhook"] = True
            result["condition"] = f"Requires potion: {obtainment}"
            return result
        # Below this line: types that do NOT bypass rarity threshold
        if any(kw in obtain_lower for kw in ["shop", "buy", "purchase", "merchant"]):
            result["type"] = "shop"
            result["condition"] = f"Shop: {obtainment}"
            return result
        if "event" in obtain_lower or "limited" in obtain_lower:
            result["type"] = "event_exclusive"
            result["condition"] = f"Event: {obtainment}"
            return result
        if "limbo" in obtain_lower:
            result["type"] = "limbo"
            result["condition"] = "Limbo exclusive"
            return result
        if "breakthrough" in obtain_lower or "bt" in obtain_lower:
            result["type"] = "breakthrough"
            result["condition"] = "Breakthrough exclusive"
            return result
        if "quest" in obtain_lower:
            result["type"] = "quest_reward"
            result["condition"] = f"Quest reward: {obtainment}"
            return result

    # --- Ultra rare: type stays normal, does NOT bypass threshold ---
    # if rarity_val is not None and rarity_val >= 10_000_000:
    #     User decides via their rarity threshold whether to notify for these.

    return result


def should_always_webhook(aura_name: str, aura_info: dict[str, Any], rarity_value: int | None = None) -> bool:
    """
    Check if an aura should ALWAYS trigger webhook regardless of threshold.

    Only these types bypass the user's minimum rarity:
      - biome_exclusive: ONLY obtainable in a specific biome
      - biome_native: significantly boosted in specific biome
      - crafted: made at a workshop
      - potion_required: requires specific potion

    Everything else (breakthrough, event, ultra-rare, normal) respects
    the user's rarity threshold.
    """
    classification = classify_aura(aura_name, aura_info)
    return classification["always_webhook"]


def get_aura_condition(aura_name: str, aura_info: dict[str, Any]) -> str:
    """Get human-readable condition for an aura."""
    classification = classify_aura(aura_name, aura_info)
    return classification["condition"]


def is_conditional_aura(aura_name: str, aura_info: dict[str, Any]) -> bool:
    """Check if an aura has special obtainment conditions."""
    classification = classify_aura(aura_name, aura_info)
    return classification["type"] != "normal" or classification["always_webhook"]


def _parse_rarity(value) -> int | None:
    """Parse rarity value from various formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace(" ", "").strip()
        if cleaned.isdigit():
            return int(cleaned)
        if "in" in cleaned.lower():
            parts = cleaned.lower().split("in")
            if len(parts) > 1:
                num = parts[-1].strip().replace(",", "")
                if num.isdigit():
                    return int(num)
    return None
