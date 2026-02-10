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
