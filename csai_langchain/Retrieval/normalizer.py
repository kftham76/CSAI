import re


def normalize_name(raw: str) -> str:
    """Normalize entity name for exact-match dedup/storage."""
    if not raw:
        return ""
    s = raw.strip()
    s = s.upper()
    s = re.sub(r'\s+', ' ', s)  # collapse whitespace
    # Normalize initial spacing: "Y. H. CHANG" -> "Y.H.CHANG"
    s = re.sub(r'(?<=\b\w\.)\s+(?=\w\.)', '', s)
    s = re.sub(r'(?<=\b\w\.)\s+(?=\w)', '', s)
    # Standardize company suffixes
    s = re.sub(r'\bSDN\.?\s*BHD\.?', 'SDN BHD', s)
    s = re.sub(r'\bS/B\b', 'SDN BHD', s)
    s = re.sub(r'\bNO\.?\b', 'NO', s)
    s = re.sub(r'\bLOT\.?\b', 'LOT', s)
    # Strip trailing noise
    return s.strip()


def normalize_match(raw: str) -> str:
    """Normalize search query — same rules as normalize_name."""
    return normalize_name(raw)
