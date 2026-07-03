#!/usr/bin/env python3
"""Extract readable text from an EPUB file, organized by chapter."""

import zipfile
import re
import os
import sys
from html.parser import HTMLParser


class TextExtractor(HTMLParser):
    """Extract text from HTML, stripping scripts/styles and inserting line breaks."""

    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6",
                   "br", "tr", "blockquote", "td", "th"):
            self.text.append("\n")

    def handle_data(self, data):
        if self.skip == 0:
            t = data.strip()
            if t:
                self.text.append(t)


def extract_epub(epub_path, output_dir=None):
    """Extract EPUB content to a plain text file, organized by chapter.

    Returns the path to the extracted text file.
    """
    if output_dir is None:
        output_dir = os.path.dirname(epub_path) or "."

    os.makedirs(output_dir, exist_ok=True)

    # Determine output filename from EPUB name
    basename = os.path.splitext(os.path.basename(epub_path))[0]
    output_file = os.path.join(output_dir, f"{basename}.txt")

    # Find all XHTML chapter files in the EPUB
    chapter_files = []
    with zipfile.ZipFile(epub_path) as z:
        for name in sorted(z.namelist()):
            if not name.endswith((".xhtml", ".html", ".htm")):
                continue
            # Skip TOC, copyright, title, dedication, notes, bibliography, index
            bn = os.path.basename(name).lower()
            if any(kw in bn for kw in ("toc", "copy", "title", "ded",
                                        "nts_", "bib", "idx", "ack", "tp_")):
                continue
            # Skip front matter files like p001, p002
            if re.search(r'p\d{3}', bn):
                continue
            chapter_files.append(name)

    if not chapter_files:
        # Fallback: include all HTML files
        with zipfile.ZipFile(epub_path) as z:
            chapter_files = [n for n in sorted(z.namelist())
                             if n.endswith((".xhtml", ".html", ".htm"))]

    with zipfile.ZipFile(epub_path) as z:
        with open(output_file, "w", encoding="utf-8") as out:
            for name in chapter_files:
                with z.open(name) as f:
                    content = f.read().decode("utf-8", errors="ignore")
                    extractor = TextExtractor()
                    extractor.feed(content)
                    text = " ".join(extractor.text)
                    text = re.sub(r"\n\s*\n", "\n\n", text)
                    text = re.sub(r" {2,}", " ", text)
                    text = re.sub(r"\n +", "\n", text)

                    chapter_label = os.path.basename(name).replace(".xhtml", "").replace(".html", "")
                    out.write(f"\n\n{'=' * 80}\n")
                    out.write(f"## Chapter block: {name}\n")
                    out.write(f"{'=' * 80}\n\n")
                    out.write(text)
                    out.write("\n\n")

    word_count = 0
    with open(output_file, "r") as f:
        word_count = len(f.read().split())

    print(f"Extracted to: {output_file}")
    print(f"Chapters: {len(chapter_files)}")
    print(f"File size: {os.path.getsize(output_file):,} bytes")
    print(f"Word count: ~{word_count:,}")

    return output_file


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: extract_epub.py <epub_path> [output_dir]")
        sys.exit(1)

    epub = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    extract_epub(epub, out)
