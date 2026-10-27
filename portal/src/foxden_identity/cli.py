from __future__ import annotations

import argparse
from pathlib import Path

from . import generate_key_files


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Fox Den Ed25519 identity signing key")
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--kid", required=True)
    args = parser.parse_args()
    generate_key_files(args.private, args.public, kid=args.kid)
    print(f"Created private key {args.private} and public trust file {args.public} for {args.kid}.")


if __name__ == "__main__":
    main()
