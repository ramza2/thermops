"""샘플 데이터 생성 스크립트."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ml"))

from ml.data_loader import get_db_url  # noqa: E402

if __name__ == "__main__":
    print(f"DB URL: {get_db_url()}")
    print("Seed data is loaded via db/init/02_seed.sql on PostgreSQL init.")
    print("Use scripts/init_db.sh to re-apply schema and seed manually.")
