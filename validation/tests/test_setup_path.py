"""The documented setup path, the setup script and the package metadata must say the same thing.

None of these tests needs the downloads or the network.
"""

import ast
import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = (REPO / "scripts" / "bootstrap.py").read_text(encoding="utf-8")
GUIDE = (REPO / "docs" / "setup.md").read_text(encoding="utf-8")


def _extras(package: str) -> set:
    with (REPO / package / "pyproject.toml").open("rb") as handle:
        return set(tomllib.load(handle)["project"]["optional-dependencies"])


def test_setup_script_is_valid_python():
    ast.parse(SCRIPT)


def test_the_extras_the_setup_installs_exist():
    install = re.search(r'"-e", "data\[([^\]]+)\]", "-e", "core\[([^\]]+)\]"', SCRIPT)
    assert install, "the install command of the setup script was not found"
    assert set(install.group(1).split(",")) <= _extras("data")
    assert set(install.group(2).split(",")) <= _extras("core")
    assert {"test", "validation"} <= _extras("core")
    assert f'-e "data[{install.group(1)}]" -e "core[{install.group(2)}]"' in GUIDE


def test_every_module_the_setup_script_runs_is_in_the_guide_and_exists():
    modules = re.findall(r'\[PYTHON, "-m", "([a-z_.]+)"((?:, "[a-z]+")*)', SCRIPT)
    names = [name for name, _ in modules if name not in ("pip", "pytest")]
    assert names == ["lsncore.ephem.fetch_kernels", "validation.pgda.fetch", "validation.lro_images.fetch", "lsn_data", "lsn_data", "lsn_data"]
    for name, arguments in modules:
        command = " ".join([f"-m {name}"] + re.findall(r'"([a-z]+)"', arguments))
        assert command in GUIDE, command
    for name in set(names):
        folder = {"lsncore": "core", "lsn_data": "data", "validation": ""}[name.split(".")[0]]
        path = REPO / folder / Path(*name.split("."))
        assert path.with_suffix(".py").exists() or (path / "__main__.py").exists(), name


def test_pinned_versions_cover_the_declared_dependencies():
    pinned = {line.split("==")[0].lower() for line in (REPO / "scripts" / "constraints.txt").read_text(encoding="utf-8").splitlines() if "==" in line}
    for package in ("core", "data"):
        with (REPO / package / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]
        declared = list(project.get("dependencies", [])) + [item for items in project["optional-dependencies"].values() for item in items]
        for requirement in declared:
            assert re.split(r"[<>=!~ ]", requirement, maxsplit=1)[0].lower() in pinned, requirement


def test_guide_names_the_data_root_and_every_folder_the_code_uses():
    for text in ("LSN_DATA_ROOT", "LSN_KERNEL_DIR", "LSN_PGDA_DIR", "LSN_LRO_DIR", "`kernels/`", "`validation/pgda/`", "`validation/lro/`", "python scripts/bootstrap.py"):
        assert text in GUIDE, text
    assert "python scripts/bootstrap.py" in (REPO / "README.md").read_text(encoding="utf-8")
