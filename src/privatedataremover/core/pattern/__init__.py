"""Page similarity and pattern grouping."""

from __future__ import annotations

import re
from dataclasses import dataclass

from privatedataremover.core.adapters.base import DocumentUnit, ExtractedSpan


_DIGIT = re.compile(r"\d")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_WS = re.compile(r"\s+")


def normalize_layout_text(text: str) -> str:
    """Strip volatile personal values so layout-like text remains."""
    t = _EMAIL.sub("@", text)
    t = _DIGIT.sub("#", t)
    t = _WS.sub(" ", t).strip().lower()
    return t


def page_fingerprint(spans: list[ExtractedSpan], unit: DocumentUnit | None = None) -> str:
    joined = " ".join(s.text for s in spans)
    norm = normalize_layout_text(joined)
    size = ""
    if unit is not None:
        size = f"|{round(unit.width)}x{round(unit.height)}"
    # Keep a bounded signature
    return (norm[:800] + size) if norm else f"empty{size}"


def similarity(a: str, b: str) -> float:
    """Simple token Jaccard + length-aware fallback."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    ta, tb = set(a.split()), set(b.split())
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        # character-level overlap for short strings
        sa, sb = set(a), set(b)
        return len(sa & sb) / len(sa | sb) if sa | sb else 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    jacc = inter / union if union else 0.0
    # Soft length penalty
    len_ratio = min(len(a), len(b)) / max(len(a), len(b))
    return 0.75 * jacc + 0.25 * len_ratio


@dataclass(frozen=True)
class PageSimilarity:
    unit_index: int
    score: float


def find_similar_pages(
    fingerprints: dict[int, str],
    seed_index: int,
    *,
    threshold: float = 0.72,
) -> list[PageSimilarity]:
    """Return pages similar to seed (excluding seed), sorted by score desc."""
    seed_fp = fingerprints.get(seed_index, "")
    results: list[PageSimilarity] = []
    for idx, fp in fingerprints.items():
        if idx == seed_index:
            continue
        score = similarity(seed_fp, fp)
        if score >= threshold:
            results.append(PageSimilarity(idx, score))
    results.sort(key=lambda p: p.score, reverse=True)
    return results


def cluster_pages(
    fingerprints: dict[int, str],
    *,
    threshold: float = 0.72,
) -> list[list[int]]:
    """Greedy clustering of similar pages."""
    remaining = sorted(fingerprints.keys())
    clusters: list[list[int]] = []
    while remaining:
        seed = remaining.pop(0)
        group = [seed]
        still: list[int] = []
        for idx in remaining:
            if similarity(fingerprints[seed], fingerprints[idx]) >= threshold:
                group.append(idx)
            else:
                still.append(idx)
        remaining = still
        clusters.append(sorted(group))
    return clusters
