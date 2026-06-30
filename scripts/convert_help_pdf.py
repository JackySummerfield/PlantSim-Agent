"""Convert the official PTS Help PDF into a markdown file ready for indexing.

This is the all-in-one convenience script for new users.  It produces a
``_code_tagged.md`` file that ``plantsim-copilot-mcp build-kb --fullmd-src``
can ingest directly.

Pipeline
--------
1. **markitdown** (fast, CPU-only) — converts the entire PDF to markdown.
   Tables may be imperfect but the textual content (SimTalk API docs)
   converts accurately.
2. **Clean** — strips page headers/footers, copyright preamble, and
   ``<!-- image -->`` artifacts that add no value.
3. **Code-tag** — wraps inline SimTalk snippets in fenced
   ````` ```simtalk ````` code blocks using the SimTalk keyword formatter
   bundled in the repo.

Requirements
------------
::

    pip install markitdown[all]

Usage
-----
::

    python scripts/convert_help_pdf.py path/to/PlantSimulation_Help.pdf

Options::

    -o, --output-dir DIR   Where to write output (default: same as input PDF)
    --skip-code-tag        Skip the SimTalk code-tagging pass
    --dry-run              Show what would happen without writing

Output
------
The script writes two files into ``--output-dir``:

- ``_markitdown_raw.md`` — raw markitdown output (kept for debugging)
- ``_code_tagged.md`` — cleaned + code-tagged, ready for indexing

After this script finishes, run::

    plantsim-copilot-mcp build-kb --fullmd-src _code_tagged.md --chapters 11,12,13,15
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Step 1: PDF → markdown via markitdown
# ---------------------------------------------------------------------------


def convert_pdf(pdf_path: Path, output_dir: Path) -> Path:
    """Run markitdown on the PDF, return path to raw .md output."""
    try:
        from markitdown import MarkItDown  # type: ignore[import-untyped]
    except ImportError:
        print(
            "ERROR: markitdown is not installed.\n"
            "  pip install markitdown[all]\n\n"
            "For higher-quality table conversion (slower, needs GPU), see:\n"
            "  docs/kb-build-guide.md → 'Option B: docling'",
            file=sys.stderr,
        )
        sys.exit(1)

    raw_out = output_dir / "_markitdown_raw.md"
    print(f"[1/3] Converting PDF → markdown via markitdown...")
    print(f"      Input:  {pdf_path}")
    print(f"      Output: {raw_out}")

    t0 = time.time()
    md = MarkItDown()
    result = md.convert(str(pdf_path))
    raw_out.write_text(result.text_content, encoding="utf-8")
    elapsed = time.time() - t0
    size_mb = raw_out.stat().st_size / (1024 * 1024)
    print(f"      Done in {elapsed:.0f}s ({size_mb:.1f} MB)")
    return raw_out


# ---------------------------------------------------------------------------
# Step 2: Clean noise (headers, footers, preamble, image placeholders)
# ---------------------------------------------------------------------------

# Matches page-header lines like "Plant Simulation Help" or "11-43"
_PAGE_HEADER_RE = re.compile(
    r"^(?:Plant Simulation Help|Objects Reference Help|SimTalk Reference"
    r"|3D Reference Help|Add-Ins Reference Help|\d+-\d+)\s*$"
)

# Matches Siemens copyright boilerplate (first ~40 lines)
_COPYRIGHT_PHRASES = (
    "Unpublished work",
    "trade secrets",
    "SIEMENS MAKES NO WARRANTY",
    "TRADEMARKS:",
    "Cybersecurity information",
    "About Siemens Digital Industries Software",
    "Support Center",
)


def clean_markdown(text: str) -> str:
    """Remove noise lines from the raw markitdown output."""
    lines = text.split("\n")
    out: list[str] = []
    skip_preamble = True  # skip everything before first # heading

    for line in lines:
        # Skip until first real heading
        if skip_preamble:
            if line.startswith("# ") and not line.startswith("# Table of Contents"):
                skip_preamble = False
            else:
                continue

        # Skip page headers/footers
        if _PAGE_HEADER_RE.match(line.strip()):
            continue

        # Skip image placeholders
        if line.strip() == "<!-- image -->":
            continue

        # Skip copyright lines that occasionally appear mid-document
        if any(phrase in line for phrase in _COPYRIGHT_PHRASES):
            continue

        out.append(line)

    # Collapse excessive blank lines (>2 consecutive)
    cleaned: list[str] = []
    blank_count = 0
    for line in out:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned.append(line)
        else:
            blank_count = 0
            cleaned.append(line)

    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Step 3: Code-tag SimTalk blocks
# ---------------------------------------------------------------------------

# Heuristic: a line that looks like SimTalk code (contains := or starts with
# a SimTalk keyword followed by typical patterns). We only tag blocks that
# are NOT already inside a fenced code block.
_SIMTALK_INDICATORS = re.compile(
    r"(?:"
    r"^(?:var|param|if|else|elseif|end|for|next|while|repeat|until|switch|case"
    r"|return|result|waituntil|stopuntil|exitloop|wait|print|println)\b"
    r"|:=|\.move\(|\.cont\b|@\.|self\.|current\."
    r")",
    re.IGNORECASE,
)


def _is_simtalk_line(line: str) -> bool:
    """Heuristic: does this line look like SimTalk code?"""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("|"):
        return False
    if stripped.startswith("```"):
        return False
    return bool(_SIMTALK_INDICATORS.search(stripped))


def code_tag_simtalk(text: str) -> str:
    """Wrap consecutive SimTalk-looking lines in fenced code blocks.

    Lines already inside a fenced block are left alone. Only tags blocks
    of 1+ consecutive SimTalk-like lines that appear between prose/heading
    lines.
    """
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    simtalk_buf: list[str] = []

    def flush_buf() -> None:
        if simtalk_buf:
            out.append("```simtalk")
            out.extend(simtalk_buf)
            out.append("```")
            simtalk_buf.clear()

    for line in lines:
        if line.strip().startswith("```"):
            flush_buf()
            in_fence = not in_fence
            out.append(line)
            continue

        if in_fence:
            out.append(line)
            continue

        if _is_simtalk_line(line):
            simtalk_buf.append(line)
        else:
            flush_buf()
            out.append(line)

    flush_buf()
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="convert_help_pdf",
        description="Convert PTS Help PDF → indexed-ready markdown (markitdown + clean + code-tag)",
    )
    parser.add_argument("pdf", type=str, help="Path to Plant Simulation Help PDF")
    parser.add_argument(
        "-o", "--output-dir", default=None, help="Output directory (default: same as PDF)"
    )
    parser.add_argument(
        "--skip-code-tag", action="store_true", help="Skip SimTalk code-tagging pass"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show plan without writing files"
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else pdf_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print(f"Would convert: {pdf_path}")
        print(f"Output dir:    {output_dir}")
        print(f"Steps:         markitdown → clean → {'code-tag' if not args.skip_code_tag else '(skip)'}")
        return 0

    # Step 1: markitdown
    raw_md_path = convert_pdf(pdf_path, output_dir)

    # Step 2: clean
    print("[2/3] Cleaning markdown (headers, footers, preamble)...")
    raw_text = raw_md_path.read_text(encoding="utf-8")
    cleaned = clean_markdown(raw_text)
    print(f"      Removed ~{len(raw_text) - len(cleaned):,} chars of noise")

    # Step 3: code-tag
    if args.skip_code_tag:
        print("[3/3] Skipping code-tag step")
        final = cleaned
    else:
        print("[3/3] Tagging SimTalk code blocks...")
        final = code_tag_simtalk(cleaned)
        block_count = final.count("```simtalk")
        print(f"      Tagged {block_count} SimTalk code blocks")

    # Write final output
    final_path = output_dir / "_code_tagged.md"
    final_path.write_text(final, encoding="utf-8")
    final_mb = final_path.stat().st_size / (1024 * 1024)
    print(f"\n✓ Output: {final_path} ({final_mb:.1f} MB)")
    print(
        f"\nNext step — index into the knowledge base:\n"
        f"  plantsim-copilot-mcp build-kb --fullmd-src \"{final_path}\" --chapters 11,12,13,15"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
