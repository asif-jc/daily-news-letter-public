"""The finite public asset set shared by private previews and release exports."""

from pathlib import Path

READER_ASSET_NAMES = (
    "editorial-curiosity.png",
    "editorial-world.png",
    "editorial-technology.png",
)


def reader_assets():
    directory = Path(__file__).parent / "assets"
    return {"assets/" + name: (directory / name).read_bytes() for name in READER_ASSET_NAMES}


def write_reader_assets(output):
    for name, content in reader_assets().items():
        path = Path(output) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
