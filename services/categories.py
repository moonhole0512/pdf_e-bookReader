"""Application-owned book categories.

Provider category paths remain stored for traceability, but the UI uses this
small vocabulary so a growing library does not inherit bookstore taxonomy.
"""

import re
from typing import Optional


APP_CATEGORIES = (
    "소설",
    "라이트 노벨",
    "만화",
    "비문학",
    "실용",
    "미분류",
)
CATEGORY_UNCLASSIFIED = "미분류"


def _compact(value: str) -> str:
    return re.sub(r"[\s·/&,+_-]+", "", (value or "").casefold())


def _is_light_novel(value: str) -> bool:
    compact = _compact(value)
    return any(token in compact for token in (
        "라이트노벨",
        "lightnovel",
        "시드노벨",
        "seednovel",
    ))


def _is_comic(value: str) -> bool:
    compact = _compact(value)
    return any(token in compact for token in (
        "만화",
        "웹툰",
        "코믹",
        "comic",
        "manga",
        "graphicnovel",
        "그래픽노블",
        "카툰",
    ))


def _source_category_hint(source_category: str) -> Optional[str]:
    parts = [part.strip() for part in re.split(r"\s*(?:>|,)\s*", source_category or "") if part.strip()]

    # A specific comic leaf wins over the broad Aladin parent
    # "만화/라이트노벨". This keeps 순정만화 classified as 만화.
    if any(_is_comic(part) and not _is_light_novel(part) for part in parts):
        return "만화"
    if any(_is_light_novel(part) for part in parts):
        return "라이트 노벨"

    combined = " ".join(parts).casefold()
    if any(token in combined for token in (
        "자기계발", "자기 개발", "경제", "경영", "비즈니스", "수험", "참고서",
        "컴퓨터", "it", "요리", "취미", "건강", "여행", "실용", "business",
    )):
        return "실용"
    if any(token in combined for token in (
        "인문", "사회", "역사", "철학", "종교", "과학", "심리", "정치", "문화",
        "예술", "에세이", "자연", "psychology", "history", "science", "nonfiction",
    )):
        return "비문학"
    if any(token in combined for token in (
        "소설", "문학", "fiction", "novel", "로맨스", "판타지", "추리", "무협", "sf",
    )):
        return "소설"
    return None


def normalize_app_category(
    category: Optional[str],
    source_category: Optional[str] = None,
) -> str:
    """Map provider-specific categories to the app's small display taxonomy."""
    label = (category or "").strip()
    source_hint = _source_category_hint(source_category or "")
    if label in APP_CATEGORIES:
        # Existing broad labels can be corrected from a more authoritative
        # provider path, while an explicit app category remains stable.
        if label == CATEGORY_UNCLASSIFIED and source_hint:
            return source_hint
        if label == "소설" and source_hint in ("실용", "비문학"):
            return source_hint
        return label

    # Prefer the provider's selected primary label. This prevents a path such
    # as "만화/라이트노벨 > 순정만화" from becoming a light novel merely
    # because its parent shelf contains the word "라이트노벨".
    if _is_light_novel(label):
        return "라이트 노벨"
    if _is_comic(label):
        return "만화"

    source = source_category or ""
    if source_hint:
        return source_hint

    combined = f"{label} {source}".casefold()
    if any(token in combined for token in (
        "소설", "문학", "fiction", "novel", "로맨스", "판타지", "추리", "무협", "sf",
    )):
        return "소설"
    if any(token in combined for token in (
        "자기계발", "자기 개발", "경제", "경영", "비즈니스", "수험", "참고서",
        "컴퓨터", "it", "요리", "취미", "건강", "여행", "실용", "business",
    )):
        return "실용"
    if any(token in combined for token in (
        "인문", "사회", "역사", "철학", "종교", "과학", "심리", "정치", "문화",
        "예술", "에세이", "자연", "psychology", "history", "science", "nonfiction",
    )):
        return "비문학"

    return CATEGORY_UNCLASSIFIED
