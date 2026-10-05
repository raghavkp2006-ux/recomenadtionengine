import csv

import pytest
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, create_engine, select

from scripts.import_imdb_ratings import import_ratings, main, read_ratings


@pytest.fixture
def catalog():
    engine = create_engine("sqlite://")
    table = Table("movies", MetaData(), Column("id", Integer, primary_key=True),
                  Column("imdb_id", String), Column("title", String),
                  Column("release_year", Integer), Column("personal_rating", Float))
    table.create(engine)
    with engine.begin() as db:
        db.execute(table.insert(), [
            dict(id=1, imdb_id="tt001", title="ID Match", release_year=2001, personal_rating=8),
            dict(id=2, imdb_id=None, title="The Film: Part II!", release_year=2002, personal_rating=9),
            dict(id=3, imdb_id="tt003", title="TV Series", release_year=2003, personal_rating=7),
            dict(id=4, imdb_id="tt004", title="Unmatched", release_year=2004, personal_rating=6),
        ])
    yield engine, table
    engine.dispose()


def export(tmp_path, rows):
    path = tmp_path / "ratings.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["Const", "Your Rating", "Title", "Year", "Title Type"])
        writer.writerows(rows)
    return path


def ratings(catalog):
    engine, table = catalog
    with engine.connect() as db:
        return dict(db.execute(select(table.c.id, table.c.personal_rating)).all())


def test_imdb_id_match(catalog, tmp_path):
    path = export(tmp_path, [["tt001", 10, "Different title", 1999, "movie"]])
    result = import_ratings(path, catalog[0])
    assert result["matched_by_imdb_id"] == 1
    assert ratings(catalog) == {1: 10, 2: 9, 3: 7, 4: 6}


def test_title_year_fallback(catalog, tmp_path):
    path = export(tmp_path, [["tt999", 5, " THE FILM PART II ", 2002, "tvMovie"]])
    result = import_ratings(path, catalog[0])
    assert result["matched_by_title_year"] == 1
    assert ratings(catalog)[2] == 5


def test_non_movie_skipped(catalog, tmp_path):
    path = export(tmp_path, [["tt003", 10, "TV Series", 2003, "tvSeries"]])
    assert import_ratings(path, catalog[0])["skipped_non_movie"] == 1
    assert ratings(catalog)[3] == 7


def test_missing_csv_exits_zero(tmp_path, capsys):
    path = tmp_path / "missing.csv"
    assert main(["--csv", str(path)]) == 0
    assert f"IMDb CSV not found at {path}; nothing imported" in capsys.readouterr().out


def test_clear_synthetic_only_unmatched(catalog, tmp_path):
    path = export(tmp_path, [["tt001", 10, "ID Match", 2001, "movie"]])
    assert import_ratings(path, catalog[0], clear_synthetic=True)["cleared"] == 3
    assert ratings(catalog) == {1: 10, 2: None, 3: None, 4: None}


def test_dry_run_writes_nothing(catalog, tmp_path):
    path = export(tmp_path, [["tt001", 10, "ID Match", 2001, "movie"]])
    before = ratings(catalog)
    import_ratings(path, catalog[0], clear_synthetic=True, dry_run=True)
    assert ratings(catalog) == before


def test_missing_columns_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Title\nMovie\n")
    with pytest.raises(ValueError, match="missing required columns"):
        read_ratings(path)


def test_invalid_rating_is_atomic(catalog, tmp_path):
    path = export(tmp_path, [["tt001", 10, "ID Match", 2001, "movie"],
                             ["tt004", "nan", "Unmatched", 2004, "movie"]])
    before = ratings(catalog)
    with pytest.raises(ValueError, match="between 1 and 10"):
        import_ratings(path, catalog[0], clear_synthetic=True)
    assert ratings(catalog) == before


def test_ambiguous_fallback_not_imported(catalog, tmp_path):
    engine, table = catalog
    with engine.begin() as db:
        db.execute(table.insert(), dict(id=5, imdb_id=None, title="The Film: Part II!",
                                      release_year=2002, personal_rating=4))
    path = export(tmp_path, [["tt999", 10, "The Film: Part II!", 2002, "movie"]])
    assert import_ratings(path, engine)["unmatched"] == 1
    assert ratings(catalog)[2] == 9
