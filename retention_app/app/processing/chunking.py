from dataclasses import dataclass


@dataclass
class TextChunk:
    start_char: int
    end_char: int
    text: str


def chunk_text(text: str, chunk_size: int = 2000) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(TextChunk(start_char=start, end_char=end, text=chunk))
        start = end
    return chunks


def stable_segment_text(text: str, target_chunk_size: int = 1200) -> list[TextChunk]:
    """Create deterministic chunks that prefer paragraph boundaries.

    Offsets always reference slices in the original cleaned text.
    """
    if not text:
        return []

    segments: list[TextChunk] = []
    cursor = 0
    pending_start = 0

    while cursor < len(text):
        split_index = text.find("\n\n", cursor)
        if split_index == -1:
            split_index = len(text)
            next_cursor = len(text)
        else:
            next_cursor = split_index + 2

        if split_index - pending_start >= target_chunk_size and split_index > pending_start:
            segments.append(
                TextChunk(
                    start_char=pending_start,
                    end_char=split_index,
                    text=text[pending_start:split_index],
                )
            )
            pending_start = next_cursor

        cursor = next_cursor

    if pending_start < len(text):
        segments.append(
            TextChunk(
                start_char=pending_start,
                end_char=len(text),
                text=text[pending_start:],
            )
        )

    if not segments:
        return [TextChunk(start_char=0, end_char=len(text), text=text)]

    return segments
