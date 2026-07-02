"""샘플 데이터 생성 스크립트."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ml"))

from ml.data_loader import get_db_url  # noqa: E402

if __name__ == "__main__":
    print(f"DB URL: {get_db_url()}")
    print("Operational seed: db/init/02_seed_clean.sql (applied on PostgreSQL init).")
    print("Test platform data: scripts/fixtures/test_platform_seed.sql (tests only, not auto-applied).")
    print("Use scripts/init_db.sh to re-apply schema and seed manually.")
