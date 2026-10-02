from dealfinder.cli import main


def test_compare_requires_input(capsys):
    assert main(["compare"]) == 2


def test_track_add_list_bought_remove(tmp_path, capsys):
    db = str(tmp_path / "p.db")
    assert main(["track", "--db", db, "add", "XM6", "--upc", "027242927896", "--target", "329"]) == 0
    assert main(["track", "--db", db, "bought", "1", "--at", "bestbuy", "--price", "449.99", "--on", "2026-09-25"]) == 0
    assert main(["track", "--db", db, "list"]) == 0
    out = capsys.readouterr().out
    assert "#1 XM6" in out and "target $329.00" in out and "bought bestbuy $449.99 on 2026-09-25" in out
    assert main(["track", "--db", db, "remove", "1"]) == 0
    main(["track", "--db", db, "list"])
    assert "XM6" not in capsys.readouterr().out


def test_track_add_needs_an_identifier(tmp_path):
    assert main(["track", "--db", str(tmp_path / "p.db"), "add", "Thing"]) == 2
