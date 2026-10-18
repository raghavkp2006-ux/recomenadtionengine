"""
scripts/schema_drift.py
Offline, read-only script to inspect schema drift between SQLAlchemy models and
a live RDS schema snapshot (scratch/live_schema.json).

IMPORTANT SAFETY GUARANTEE:
This script NEVER connects to a real or remote database. To prevent database.py's
import-time `init_db()` (which executes `create_all()`, schema migrations, and catalog
seeding) from touching any live RDS or PostgreSQL instance, `DATABASE_URL` is forced
to `sqlite:///:memory:` before any project modules are imported.

HOW `scratch/live_schema.json` IS PRODUCED:
The schema snapshot is generated via an inspect-only one-off ECS task running on AWS
against the live RDS instance without applying any DDL:

1. Create scratch/overrides.json:
{
  "containerOverrides": [
    {
      "name": "recommendation-api",
      "command": [
        "python",
        "-c",
        "import database, sqlalchemy, json; insp = sqlalchemy.inspect(database.engine); tables = insp.get_table_names(); schema = {t: [c['name'] for c in insp.get_columns(t)] for t in tables}; print('---LIVE_DB_SCHEMA_START---'); print(json.dumps(schema)); print('---LIVE_DB_SCHEMA_END---')"
      ]
    }
  ]
}

2. Launch one-off ECS inspection task:
aws ecs run-task \
  --cluster <CLUSTER_NAME> \
  --task-definition <TASK_DEFINITION> \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<SUBNET_ID>],securityGroups=[<SECURITY_GROUP_ID>],assignPublicIp=ENABLED}" \
  --overrides file://scratch/overrides.json \
  --region ap-south-1

3. Extract CloudWatch log output between ---LIVE_DB_SCHEMA_START--- and ---LIVE_DB_SCHEMA_END---
   and save into scratch/live_schema.json.
"""

import os
import sys

# 1. Force in-memory SQLite before ANY project import so init_db() at import time
# touches only volatile memory and never a real or remote database.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json

# Project imports (loads Base metadata for all registered models)
from database import Base  # type: ignore
import models.profile  # type: ignore
import models.myntra  # type: ignore


def check_schema_drift():
    live_schema_path = os.path.join(
        os.path.dirname(__file__), "..", "scratch", "live_schema.json"
    )

    if not os.path.exists(live_schema_path):
        print(
            f"ERROR: Live database schema snapshot not found at '{live_schema_path}'.\n"
            "This script is strictly offline/read-only and will not connect to a live database.\n"
            "Please generate scratch/live_schema.json using the one-off ECS inspection command "
            "documented in the module docstring.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(live_schema_path, "r", encoding="utf-8") as f:
        live_db = json.load(f)

    db_tables = set(live_db.keys())
    get_db_columns = lambda tbl: set(live_db.get(tbl, []))
    dialect_str = "postgresql (snapshot from scratch/live_schema.json)"

    model_tables = set(Base.metadata.tables.keys())
    missing_tables = model_tables - db_tables

    print(f"Target Database: {dialect_str}")
    print("\n=== (a) Tables in models but missing in DB ===")
    if missing_tables:
        for t in sorted(missing_tables):
            print(f"  - {t}")
    else:
        print("  [OK] None.")

    print("\n=== (b) Columns in models but missing in DB per table ===")
    drift_found = False
    for table_name in sorted(model_tables & db_tables):
        model_cols = {
            col.name: str(col.type)
            for col in Base.metadata.tables[table_name].columns
        }
        db_cols = get_db_columns(table_name)
        missing_cols = set(model_cols.keys()) - db_cols
        if missing_cols:
            drift_found = True
            print(f"Table '{table_name}' missing columns in DB:")
            for col_name in sorted(missing_cols):
                print(f"  - {col_name} ({model_cols[col_name]})")

    if not drift_found:
        print("  [OK] None. All existing tables have all model columns.")


if __name__ == "__main__":
    check_schema_drift()
