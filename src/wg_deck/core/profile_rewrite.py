"""Lossless update of supported WireGuard fields, preserving comments and style.

Existing configs containing unknown directives or executable hooks are NOT
silently reserialized: they remain preview-only and can be exported unchanged.
"""
from __future__ import annotations

from .profile_export import (
    ProfileDraft, ProfileValidationError, parse_supported_profile, render_new_profile,
)


def rewrite_supported_config(name: str, original: str, draft: ProfileDraft) -> str:
    parse_supported_profile(name, original)
    if draft.name != name:
        raise ProfileValidationError("Existing profile cannot be renamed.")
    # Validate every new field before opening or modifying the original document.
    canonical = render_new_profile(draft)
    newline = "\r\n" if "\r\n" in original else "\n"

    def parse_segments(text: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
        preamble: list[str] = []
        segments: list[tuple[str, list[str]]] = []
        current: list[str] | None = None
        kind = ""
        for raw in text.splitlines(keepends=True):
            stripped = raw.strip()
            if stripped in ("[Interface]", "[Peer]"):
                kind = "interface" if stripped == "[Interface]" else "peer"
                current = [raw]
                segments.append((kind, current))
            elif current is None:
                preamble.append(raw)
            else:
                current.append(raw)
        return preamble, segments

    preamble, old_segments = parse_segments(original)
    _, new_segments = parse_segments(canonical)
    old_peers = sum(k == "peer" for k, _ in old_segments)
    if not old_segments or old_segments[0][0] != "interface":
        raise ProfileValidationError("Unsupported section ordering.")
    # Reserialize only known/validated values. Merge fields by key, retain
    # original comments, blank lines, casing, indentation and line endings.
    result = list(preamble)
    for index, (kind, target) in enumerate(new_segments):
        desired: dict[str, str] = {}
        for line in target[1:]:
            if "=" in line:
                key, value = (part.strip() for part in line.split("=", 1))
                desired[key.casefold()] = value

        if index >= len(old_segments):
            result.extend(line.rstrip("\r\n") + newline for line in target)
            continue
        old_kind, old_lines = old_segments[index]
        if kind != old_kind:
            raise ProfileValidationError("Unsupported change to section ordering.")
        used: set[str] = set()
        result.append(old_lines[0])
        for line in old_lines[1:]:
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", ";")) or "=" not in line:
                result.append(line)
                continue
            key, _ = (part.strip() for part in stripped.split("=", 1))
            normalized = key.casefold()
            if normalized not in desired:
                # A field omitted intentionally by the edited validated profile.
                continue
            used.add(normalized)
            original_left, original_right = line.split("=", 1)
            preserved_space = original_right[:len(original_right) - len(original_right.lstrip())]
            line_ending = "\r\n" if line.endswith("\r\n") else "\n"
            result.append(
                f"{original_left}={preserved_space}{desired[normalized]}{line_ending}"
            )
        for field, value in desired.items():
            if field not in used:
                title = next(
                    (line.split("=", 1)[0].strip() for line in target[1:]
                     if "=" in line and line.split("=", 1)[0].strip().casefold() == field),
                    field,
                )
                result.append(f"{title} = {value}{newline}")

    # Dropped peer sections are intentional user removals; unrelated interface
    # comments/fields are preserved. New peers append as validated sections.
    rewritten = "".join(result)
    if not rewritten.endswith(("\n", "\r")):
        rewritten += newline
    verified = parse_supported_profile(name, rewritten)
    # Ignore cosmetic whitespace differences while comparing validated data.
    if render_new_profile(verified) != render_new_profile(draft):
        raise ProfileValidationError("Cannot preserve configuration accurately.")
    return rewritten
