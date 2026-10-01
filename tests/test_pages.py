import json
from pathlib import Path

import pytest

from scripts.build_pages import Site, normalize_base
from scripts.pages_check import verify_artifact


def test_static_site_links_evidence_and_allowlisted_files(tmp_path):
    site = Site(tmp_path / "site").build()
    verify_artifact(site, "/practical-eval-lab/")
    catalog = json.loads(next((site / "samples").glob("catalog-*.json")).read_text(encoding="utf-8"))
    assert len(catalog["recordings"]) == 6
    assert len(list((site / "reports").glob("*.json"))) == 12
    assert (site / "downloads/anthropic-MIT.txt").read_text(encoding="utf-8").startswith("MIT License")
    assert (site / "architecture/pipeline.drawio").is_file()
    assert not (site / "api").exists()
    assert not (site / "eval_lab").exists()
    assert not (site / ".github").exists()
    assert "data-mode=\"public\"" in (site / "index.html").read_text(encoding="utf-8")
    # A repeat build removes obsolete generated files, but refuses unrelated directories.
    (site / "obsolete.html").write_text("old", encoding="utf-8")
    Site(site).build()
    assert not (site / "obsolete.html").exists()


def test_build_preserves_unrelated_output_and_rejects_invalid_base_paths(tmp_path):
    (tmp_path / "valuable.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="empty or a previous"):
        Site(tmp_path)
    assert (tmp_path / "valuable.txt").read_text(encoding="utf-8") == "keep"
    for value in ("relative/", "/project", "/../", "//external.example/"):
        with pytest.raises(ValueError):
            normalize_base(value)
    with pytest.raises(ValueError, match="source tree"):
        Site(Path(__file__).resolve().parent.parent)
