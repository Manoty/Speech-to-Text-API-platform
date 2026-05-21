"""
app/domains/transcriptions/export.py

Generates SRT and VTT subtitle files from stored word segments.
Pure Python — no external dependencies.

SRT format:
    1
    00:00:00,000 --> 00:00:04,500
    Hello world this is the first segment.

VTT format:
    WEBVTT

    00:00:00.000 --> 00:00:04.500
    Hello world this is the first segment.
"""

from app.domains.transcriptions.models import Transcript


def _format_srt_time(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_vtt_time(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    s = int(seconds) % 60
    m = int(seconds // 60) % 60
    h = int(seconds // 3600)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _group_segments_into_lines(
    segments: list[dict],
    max_words_per_line: int = 10,
) -> list[dict]:
    """
    Group word-level segments into subtitle lines.
    Each line has: start, end, text
    """
    lines = []
    current_words: list[str] = []
    line_start: float | None = None
    line_end: float = 0.0

    for seg in segments:
        word = seg.get("word", "").strip()
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)

        if not word:
            continue

        if line_start is None:
            line_start = start

        current_words.append(word)
        line_end = end

        if len(current_words) >= max_words_per_line:
            lines.append({
                "start": line_start,
                "end": line_end,
                "text": " ".join(current_words),
            })
            current_words = []
            line_start = None

    if current_words and line_start is not None:
        lines.append({
            "start": line_start,
            "end": line_end,
            "text": " ".join(current_words),
        })

    return lines


def _fallback_lines(full_text: str, duration: float) -> list[dict]:
    """
    When no word-level segments exist, split text evenly across duration.
    Used when whisper_word_timestamps was False.
    """
    words = full_text.split()
    if not words or not duration:
        return [{"start": 0.0, "end": duration or 0.0, "text": full_text}]

    chunk_size = 10
    chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
    time_per_chunk = duration / len(chunks)

    return [
        {
            "start": i * time_per_chunk,
            "end": (i + 1) * time_per_chunk,
            "text": " ".join(chunk),
        }
        for i, chunk in enumerate(chunks)
    ]


def generate_srt(transcript: Transcript) -> str:
    if transcript.segments:
        lines = _group_segments_into_lines(transcript.segments)
    else:
        lines = _fallback_lines(
            transcript.full_text, transcript.duration_seconds or 0.0
        )

    blocks = []
    for i, line in enumerate(lines, start=1):
        start = _format_srt_time(line["start"])
        end = _format_srt_time(line["end"])
        blocks.append(f"{i}\n{start} --> {end}\n{line['text']}")

    return "\n\n".join(blocks)


def generate_vtt(transcript: Transcript) -> str:
    if transcript.segments:
        lines = _group_segments_into_lines(transcript.segments)
    else:
        lines = _fallback_lines(
            transcript.full_text, transcript.duration_seconds or 0.0
        )

    blocks = ["WEBVTT\n"]
    for line in lines:
        start = _format_vtt_time(line["start"])
        end = _format_vtt_time(line["end"])
        blocks.append(f"{start} --> {end}\n{line['text']}")

    return "\n\n".join(blocks)


def generate_txt(transcript: Transcript) -> str:
    return transcript.full_text