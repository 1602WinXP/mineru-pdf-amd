#!/usr/bin/env python3
"""MinerU Markdown cleaner: MM_MD -> NLP_MD (removes <details> blocks)"""

import argparse
import os
import re
import sys


def clean_markdown(text):
    """Convert MM_MD to NLP_MD style markdown"""
    # Remove <details>...</details> blocks
    text = re.sub(r'\n?<details>\s*\n<summary>.*?</summary>\s*\n.*?</details>\s*\n?',
                  '\n', text, flags=re.DOTALL)
    text = re.sub(r'<details>.*?</details>', '', text, flags=re.DOTALL)
    text = re.sub(r'</?details>', '', text)
    text = re.sub(r'<summary>.*?</summary>', '', text)
    # Clean extra blank lines
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + '\n'


def main():
    parser = argparse.ArgumentParser(description="MM_MD -> NLP_MD markdown cleaner")
    parser.add_argument("input", help="Input markdown file")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        raw = f.read()

    cleaned = clean_markdown(raw)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(cleaned)
        print(f"{args.input} ({len(raw):,}c) -> {args.output} ({len(cleaned):,}c)"
              f" (-{(1-len(cleaned)/len(raw))*100:.0f}%)")
    else:
        sys.stdout.write(cleaned)


if __name__ == "__main__":
    main()
