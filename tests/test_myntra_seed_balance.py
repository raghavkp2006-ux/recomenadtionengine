import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.myntra import MyntraProduct
from scripts import seed_myntra_products as seeder


@pytest.fixture
def skewed_csv(tmp_path):
    df = pd.DataFrame({"product_id": range(100),
                       "title": [f"Product {i}" for i in range(100)],
                       "ideal_for": ["Women"] * 90 + ["Men"] * 10})
    path = tmp_path / "products.csv"
    df.to_csv(path, index=False)
    return df, path


def test_balanced_skewed_fixture_and_deterministic(skewed_csv):
    df, _ = skewed_csv
    sampled = seeder.sample_by_gender(df, 20)
    counts = sampled.ideal_for.value_counts()
    print("90/10 fixture, limit=20:")
    print(counts.to_string())
    assert len(sampled) == 20
    assert all(abs(count / len(sampled) - 0.5) <= 0.05 for count in counts)
    pd.testing.assert_frame_equal(sampled, seeder.sample_by_gender(df, 20))


def test_shortage_redistributed(skewed_csv):
    df, _ = skewed_csv
    sampled = seeder.sample_by_gender(df, 50)
    assert sampled.ideal_for.value_counts().to_dict() == {"Women": 40, "Men": 10}
    assert len(sampled) == 50


def test_seed_rerun_idempotent(skewed_csv, monkeypatch):
    _, path = skewed_csv
    engine = create_engine("sqlite://")
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(seeder, "engine", engine)
    monkeypatch.setattr(seeder, "SessionLocal", factory)
    seeder.seed(str(path), limit=20, batch_size=7)
    with factory() as db:
        before = {row.product_id: row.gender for row in db.query(MyntraProduct).all()}
    seeder.seed(str(path), limit=20, batch_size=7)
    with factory() as db:
        after = {row.product_id: row.gender for row in db.query(MyntraProduct).all()}
        assert db.query(MyntraProduct).count() == 20
    assert before == after
    assert list(after.values()).count("Men") == list(after.values()).count("Women") == 10
    engine.dispose()


def test_default_limit_is_500():
    df = pd.DataFrame({"gender": ["women"] * 900 + ["men"] * 900})
    assert seeder.sample_by_gender(df).gender.value_counts().to_dict() == {"men": 250, "women": 250}


def test_unique_products_before_sampling(skewed_csv):
    df, _ = skewed_csv
    duplicate = pd.concat([df, df], ignore_index=True)
    sample = seeder.sample_by_gender(duplicate, 20)
    assert sample.product_id.nunique() == 20
    assert sample.ideal_for.value_counts().to_dict() == {"Men": 10, "Women": 10}


def test_small_empty_and_invalid_limits(skewed_csv):
    df, _ = skewed_csv
    assert len(seeder.sample_by_gender(df, 500)) == 100
    assert seeder.sample_by_gender(df.iloc[:0], 20).empty
    assert seeder.sample_by_gender(df, 0).empty
    with pytest.raises(ValueError, match="nonnegative"):
        seeder.sample_by_gender(df, -1)


def test_missing_gender_column_rejected():
    with pytest.raises(ValueError, match="ideal_for or gender"):
        seeder.sample_by_gender(pd.DataFrame({"title": ["No gender"]}), 1)
