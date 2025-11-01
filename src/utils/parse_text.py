"""
Command-line script to parse text and create a JSON object.
"""
import argparse
import json
import sys
from text_parser import parse_text_to_json

def main():
    """
    Parse text from a file or stdin and output a JSON object.
    """
    parser = argparse.ArgumentParser(description="Parse text and create a JSON object with findings and background sections.")
    parser.add_argument("--input", "-i", help="Input file path. If not provided, reads from stdin.")
    parser.add_argument("--output", "-o", help="Output file path. If not provided, prints to stdout.")
    args = parser.parse_args()

    # Read input text
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    # Parse text to JSON
    result = parse_text_to_json(text)

    # Output JSON
    json_result = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_result)
    else:
        print(json_result)

if __name__ == "__main__":
    main()
