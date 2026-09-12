"""
Seed script to populate the myntra_products catalog from a real dataset.

Reads CSV from data/myntra_seed/myntra_products.csv (or a specified path),
maps fields to MyntraProduct schema, and inserts products idempotently.
Respects DATABASE_URL from database.py.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, SessionLocal, engine
from models.myntra import MyntraProduct


def parse_specs(spec_str: Any) -> Dict[str, str]:
    if not isinstance(spec_str, str):
        return {}
    specs = {}
    for part in spec_str.split("|"):
        if ":" in part:
            k, v = part.split(":", 1)
            specs[k.strip().lower()] = v.strip()
    return specs


def extract_category_and_sub(type_str: Any, product_type: Any):
    cat = None
    subcat = None
    if isinstance(type_str, str) and "/" in type_str:
        parts = [p.strip() for p in type_str.split("/") if p.strip()]
        if len(parts) >= 3:
            cat = parts[2]
            if len(parts) >= 4 and not parts[3].lower().startswith("more by"):
                subcat = parts[3]
        elif len(parts) >= 1:
            cat = parts[-1]
    
    if not cat and isinstance(product_type, str) and product_type.strip():
        cat = product_type.strip()
    if not subcat and isinstance(product_type, str) and product_type.strip():
        subcat = product_type.strip()

    return cat or "Apparel", subcat or cat or "Apparel"


def clean_str(val: Any) -> Optional[str]:
    if pd.isna(val) or val is None:
        return None
    s = str(val).strip()
    return s if s else None


def clean_float(val: Any) -> Optional[float]:
    if pd.isna(val) or val is None:
        return None
    try:
        f = float(val)
        return f if f >= 0 else None
    except (ValueError, TypeError):
        return None


def extract_first_image(images_str: Any) -> Optional[str]:
    if not isinstance(images_str, str):
        return None
    for img in images_str.split("|"):
        img = img.strip()
        if img.startswith("http://") or img.startswith("https://"):
            return img
    return None


def map_row_to_product(row: pd.Series, index: int, now: datetime) -> Optional[Dict[str, Any]]:
    # 1. Product ID
    raw_pid = row.get("product_id")
    if pd.notna(raw_pid):
        pid_str = str(int(raw_pid) if isinstance(raw_pid, float) and raw_pid.is_integer() else raw_pid).strip()
    else:
        pid_str = f"seed-{index}"
    
    # 2. Product URL / link
    link = clean_str(row.get("link"))
    if not link:
        link = f"https://www.myntra.com/product/{pid_str}"

    brand = clean_str(row.get("brand"))
    title = clean_str(row.get("title"))
    if not title:
        return None

    cat, subcat = extract_category_and_sub(row.get("type"), row.get("product_type"))
    gender = clean_str(row.get("ideal_for"))

    price = clean_float(row.get("variant_price"))
    mrp = clean_float(row.get("variant_compare_at_price"))
    if price and not mrp:
        mrp = price
    elif mrp and not price:
        price = mrp

    discount_pct = None
    if mrp and price and mrp > price:
        discount_pct = round((1 - price / mrp) * 100, 2)

    specs = parse_specs(row.get("specifications") or row.get("inventory"))
    colour = clean_str(row.get("dominant_color")) or clean_str(row.get("actual_color"))
    if not colour and "colour family" in specs:
        colour = specs["colour family"]

    raw_size = clean_str(row.get("size"))
    sizes = [s.strip() for s in raw_size.split(",") if s.strip()] if raw_size else []

    fit = clean_str(row.get("size_fit")) or specs.get("fit") or specs.get("type")
    material = clean_str(row.get("dominant_material")) or specs.get("fabric")
    pattern = specs.get("pattern") or specs.get("print or pattern type")
    occasion = specs.get("occasion")

    image_url = extract_first_image(row.get("images"))

    attrs = {
        "care_instructions": clean_str(row.get("care_instructions")),
        "product_type": clean_str(row.get("product_type")),
        "body": clean_str(row.get("body")),
    }
    attrs = {k: v for k, v in attrs.items() if v is not None}

    return {
        "product_id": pid_str,
        "product_url": link,
        "brand": brand,
        "title": title,
        "category": cat,
        "subcategory": subcat,
        "gender": gender,
        "price": price,
        "mrp": mrp,
        "discount_percent": discount_pct,
        "currency": "INR",
        "rating": None,
        "rating_count": None,
        "colour": colour,
        "sizes_json": json.dumps(sizes),
        "fit": fit,
        "material": material,
        "pattern": pattern,
        "occasion": occasion,
        "season": None,
        "seller": None,
        "image_url": image_url,
        "attributes_json": json.dumps(attrs, ensure_ascii=False),
        "first_seen_at": now,
        "last_seen_at": now,
    }


def seed(csv_path: str, limit: Optional[int] = None, dry_run: bool = False, batch_size: int = 500):
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        sys.exit(1)

    print(f"Reading dataset from: {csv_path}")
    df = pd.read_csv(csv_path, on_bad_lines="skip", low_memory=False)
    total_in_csv = len(df)
    print(f"Loaded {total_in_csv} rows from CSV.")

    if limit is not None and limit > 0:
        df = df.iloc[:limit]
        print(f"Applying limit: processing first {len(df)} rows.")

    db = SessionLocal()
    try:
        # Ensure tables exist
        Base.metadata.create_all(bind=engine)

        print("Querying existing product_ids from database...")
        existing_tuples = db.query(MyntraProduct.product_id).all()
        existing_ids = {t[0] for t in existing_tuples}
        print(f"Database currently contains {len(existing_ids)} product(s).")

        now = datetime.now(timezone.utc)
        inserted_count = 0
        skipped_count = 0
        batch: List[MyntraProduct] = []

        # Track IDs seen within this run to avoid duplicates within CSV itself
        seen_in_run = set(existing_ids)

        for idx, row in df.iterrows():
            product_dict = map_row_to_product(row, idx, now)
            if not product_dict:
                skipped_count += 1
                continue

            pid = product_dict["product_id"]
            if pid in seen_in_run:
                skipped_count += 1
                continue

            seen_in_run.add(pid)

            if dry_run:
                inserted_count += 1
                if inserted_count <= 5:
                    print(f"\n[DRY RUN Sample #{inserted_count}]")
                    for k in ("product_id", "brand", "title", "category", "gender", "price", "mrp", "discount_percent", "colour", "image_url"):
                        print(f"  {k}: {product_dict.get(k)}")
                continue

            batch.append(MyntraProduct(**product_dict))
            inserted_count += 1

            if len(batch) >= batch_size:
                db.bulk_save_objects(batch)
                db.commit()
                print(f"Committed batch of {len(batch)} products (total inserted so far: {inserted_count})...")
                batch = []

        if not dry_run and batch:
            db.bulk_save_objects(batch)
            db.commit()
            print(f"Committed final batch of {len(batch)} products.")

        print("\n" + "=" * 50)
        print("SEEDING SUMMARY:")
        print(f"  Mode: {'DRY RUN (no database writes)' if dry_run else 'LIVE INSERT'}")
        print(f"  Total processed: {len(df)}")
        print(f"  Inserted (new): {inserted_count}")
        print(f"  Skipped (duplicates/invalid): {skipped_count}")
        print(f"  Final database count: {len(existing_ids) + (0 if dry_run else inserted_count)}")
        print("=" * 50)

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed MyntraProduct catalog from a CSV dataset.")
    parser.add_argument(
        "--csv",
        type=str,
        default="data/myntra_seed/myntra_products.csv",
        help="Path to the Myntra CSV file (default: data/myntra_seed/myntra_products.csv)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of rows to process")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing to database")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch commit size")
    args = parser.parse_args()

    seed(csv_path=args.csv, limit=args.limit, dry_run=args.dry_run, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
