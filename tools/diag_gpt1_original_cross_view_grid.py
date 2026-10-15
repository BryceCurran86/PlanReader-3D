"""Prove original native plan-grid control alignment, not physical correspondence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_source_grid_registration_shadow import source_grid_registration_shadow


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--sha256",required=True)
    parser.add_argument("--first-page",type=int,required=True)
    parser.add_argument("--second-page",type=int,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    result=source_grid_registration_shadow(
        args.pdf.read_bytes(),expected_sha256=args.sha256,
        first_page_index=args.first_page-1,second_page_index=args.second_page-1,
    )
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
