"""Fetch exact, MIT/OFL-licensed browser assets from the public npm registry.

This maintainer command is unnecessary for installation: assets are committed.
Tarball integrity is verified against npm's SHA-512 metadata before copying an
explicit allowlist of files. No archive paths are extracted onto the filesystem.
"""

import base64
import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app" / "static" / "vendor"
PACKAGES = {
    "bootstrap": (
        "5.3.8",
        {
            "dist/css/bootstrap.min.css": "bootstrap/bootstrap.min.css",
            "dist/css/bootstrap.min.css.map": "bootstrap/bootstrap.min.css.map",
            "dist/js/bootstrap.bundle.min.js": "bootstrap/bootstrap.bundle.min.js",
            "dist/js/bootstrap.bundle.min.js.map": "bootstrap/bootstrap.bundle.min.js.map",
            "LICENSE": "bootstrap/LICENSE",
        },
    ),
    "bootstrap-icons": (
        "1.13.1",
        {
            "font/bootstrap-icons.min.css": "bootstrap-icons/bootstrap-icons.min.css",
            "font/fonts/bootstrap-icons.woff": "bootstrap-icons/fonts/bootstrap-icons.woff",
            "font/fonts/bootstrap-icons.woff2": "bootstrap-icons/fonts/bootstrap-icons.woff2",
            "LICENSE": "bootstrap-icons/LICENSE",
        },
    ),
    "chart.js": (
        "4.5.1",
        {
            "dist/chart.umd.min.js": "chartjs/chart.umd.min.js",
            "dist/chart.umd.min.js.map": "chartjs/chart.umd.min.js.map",
            "LICENSE.md": "chartjs/LICENSE.md",
        },
    ),
    "@fontsource/manrope": (
        "5.2.8",
        {
            **{
                f"files/manrope-latin-{weight}-normal.woff2": f"fonts/manrope-latin-{weight}-normal.woff2"
                for weight in (400, 600, 700, 800)
            },
            "LICENSE": "fonts/LICENSE",
        },
    ),
}


def fetch_assets():
    for name, (version, files) in PACKAGES.items():
        url = f"https://registry.npmjs.org/{name}/{version}"
        with urllib.request.urlopen(url, timeout=30) as response:
            metadata = json.load(response)
        with urllib.request.urlopen(
            metadata["dist"]["tarball"], timeout=60
        ) as response:
            archive_bytes = response.read()
        algorithm, expected = metadata["dist"]["integrity"].split("-", 1)
        digest = base64.b64encode(
            hashlib.new(algorithm, archive_bytes).digest()
        ).decode()
        if digest != expected:
            raise RuntimeError(f"Integrity mismatch for {name}")
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            for source, destination in files.items():
                content = archive.extractfile(f"package/{source}").read()
                path = ROOT / destination
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        print(f"Vendored {name}@{version} ({len(files)} files)")


if __name__ == "__main__":
    fetch_assets()
