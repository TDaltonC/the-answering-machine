import re


def parse_agent_picks(text: str) -> list[dict]:
    """Parse FINAL PICKS text into structured book data."""
    books = []
    for match in re.finditer(
        r'"([^"]+)"\s+by\s+([^—\n]+?)(?:\s*—\s*(.+?))?(?:\n|$)',
        text,
    ):
        title = match.group(1)
        author = match.group(2).strip().strip("*")
        reason = (match.group(3) or "").strip().rstrip(". ")
        if ". Available at" in reason:
            reason = reason.split(". Available at")[0]
        books.append({"title": title, "author": author, "why": reason})
    return books
