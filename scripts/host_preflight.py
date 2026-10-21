"""Read-only preflight: python scripts/host_preflight.py --database-url sqlite:///backup.db."""

from sqlalchemy import create_engine
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MARZBAN_CLI", "1")


def main():
    parser = argparse.ArgumentParser(description="Check legacy hosts before the unified-host migration")
    parser.add_argument("--database-url", required=True, help="Database copy to inspect; no rows are written")
    args = parser.parse_args()
    from app.db.migrations.host_redesign_v1 import preflight

    engine = create_engine(args.database_url)
    with engine.connect() as connection:
        report = preflight(connection)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
