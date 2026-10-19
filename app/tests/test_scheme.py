from pathlib import Path

from gemstudio.scheme import content_type, resolve_request_path


def make_tree(tmp_path: Path):
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "fights.html").write_text("<html>")
    (web / "assets" / "app.js").write_text("export {}")
    data = tmp_path / "data"
    (data / "fights").mkdir(parents=True)
    (data / "fights" / "7.json").write_text("{}")
    extra = tmp_path / "public"
    (extra / "figures").mkdir(parents=True)
    (extra / "figures" / "map.webp").write_bytes(b"RIFF")
    (tmp_path / "secret.txt").write_text("secret")
    return web, [data, extra]


def test_serves_figure_files_and_the_default_page(tmp_path):
    web, roots = make_tree(tmp_path)
    assert resolve_request_path("/", web, roots) == (web / "fights.html").resolve()
    assert resolve_request_path("/assets/app.js", web, roots) == (web / "assets/app.js").resolve()


def test_serves_data_from_the_first_root_that_has_the_file(tmp_path):
    web, roots = make_tree(tmp_path)
    assert resolve_request_path("/_data/fights/7.json", web, roots).name == "7.json"
    assert resolve_request_path("/_data/figures/map.webp", web, roots).name == "map.webp"


def test_missing_files_are_not_found(tmp_path):
    web, roots = make_tree(tmp_path)
    assert resolve_request_path("/nope.js", web, roots) is None
    assert resolve_request_path("/_data/fights/99.json", web, roots) is None


def test_refuses_to_leave_the_served_folders(tmp_path):
    web, roots = make_tree(tmp_path)
    assert resolve_request_path("/../secret.txt", web, roots) is None
    assert resolve_request_path("/%2e%2e/secret.txt", web, roots) is None
    assert resolve_request_path("/_data/../secret.txt", web, roots) is None


def test_module_scripts_get_a_javascript_type():
    assert content_type(Path("fights-abc.js")) == "text/javascript"
    assert content_type(Path("map.webp")) == "image/webp"
    assert content_type(Path("x.woff2")) == "font/woff2"


def test_qts_webchannel_script_is_available_to_serve():
    from gemstudio.scheme import channel_script

    script = channel_script()
    assert script is not None and b"QWebChannel" in script
