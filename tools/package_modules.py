#!/usr/bin/env python3
"""Build deterministic, self-contained ZIP files for Open HVAC modules.

Only explicitly catalogued paths are packed. No Home Assistant runtime needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "modules" / "catalog.json"
SAFE_PREFIXES = ("custom_components/", "blueprints/", "www/", "examples/", "esp32_s3/")
ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def module_catalog() -> list[dict]:
    """Validate the allowlisted distribution catalog."""
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    if doc.get("schema_version") != 1 or not isinstance(doc.get("modules"), list):
        raise ValueError("Invalid module catalog version or module list")
    seen: set[str] = set()
    modules = doc["modules"]
    if not modules:
        raise ValueError("Module catalog cannot be empty")
    for module in modules:
        slug = module.get("slug")
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError("Invalid module slug")
        if slug in seen:
            raise ValueError(f"Duplicate module slug: {slug}")
        seen.add(slug)
        if not isinstance(module.get("paths"), list) or not module["paths"]:
            raise ValueError(f"Missing paths: {slug}")
        for name in module["paths"]:
            safe_relative_path(name)
            if not any(name == prefix.rstrip("/") or name.startswith(prefix) for prefix in SAFE_PREFIXES):
                raise ValueError(f"Disallowed catalog path: {name}")
            if not (ROOT / name).exists():
                raise ValueError(f"Missing module content: {name}")
        for field in ("name", "kind", "status", "summary", "documentation", "target", "caution"):
            if not isinstance(module.get(field), str) or not module[field].strip():
                raise ValueError(f"Missing {field} for {slug}")
        safe_relative_path(module["documentation"])
    return modules


def safe_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or "\\" in value or value.startswith("/"):
        raise ValueError(f"Not a safe relative path: {value!r}")
    item = PurePosixPath(value)
    if not value or any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError(f"Path traversal or invalid path: {value!r}")
    if item.is_absolute() or item.parts[0].startswith("."):
        raise ValueError(f"Unsafe path: {value!r}")
    return item


def module_files(module: dict) -> list[Path]:
    """Return only regular files inside explicitly selected directories."""
    collected: dict[str, Path] = {}
    for name in module["paths"]:
        target = ROOT / name
        if target.is_symlink():
            raise ValueError(f"Symlink in catalog: {target}")
        candidates = target.rglob("*") if target.is_dir() else [target]
        for path in candidates:
            if path.is_symlink():
                raise ValueError(f"Symlink in module: {path}")
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            safe_relative_path(relative)
            if any(p.startswith(".") or p == "__pycache__" for p in path.relative_to(ROOT).parts):
                raise ValueError(f"Hidden or generated file: {relative}")
            if path.stat().st_size > 10 * 1024 * 1024:
                raise ValueError(f"File unexpectedly large: {relative}")
            collected[relative] = path
    if not collected:
        raise ValueError(f"Empty module: {module['slug']}")
    return [collected[key] for key in sorted(collected)]


def make_zip(module: dict, output: Path) -> None:
    files = module_files(module)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            info = ZipInfo(relative, date_time=ZIP_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    verify_zip(module, output)


def verify_zip(module: dict, archive_path: Path) -> None:
    expected = {p.relative_to(ROOT).as_posix(): p for p in module_files(module)}
    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError(f"Archive contents mismatch: {module['slug']}")
        for name in names:
            safe_relative_path(name)
            if hashlib.sha256(archive.read(name)).digest() != hashlib.sha256(expected[name].read_bytes()).digest():
                raise ValueError(f"Archive checksum mismatch: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="Local output directory")
    parser.add_argument("--module", action="append", help="Module slug; repeat to select multiple")
    parser.add_argument("--verify", action="store_true", help="Only verify packages already built")
    args = parser.parse_args()
    modules = module_catalog()
    choices = set(args.module or [m["slug"] for m in modules])
    unknown = choices - {m["slug"] for m in modules}
    if unknown:
        parser.error(f"Unknown module(s): {sorted(unknown)}")
    args.out.mkdir(parents=True, exist_ok=True)
    checksums = []
    for module in modules:
        if module["slug"] not in choices:
            continue
        zip_path = args.out / f"open-hvac-{module['slug']}.zip"
        if args.verify:
            verify_zip(module, zip_path)
        else:
            make_zip(module, zip_path)
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        checksums.append(f"{digest}  {zip_path.name}")
        print(f"{module['slug']}: {len(module_files(module))} files, {zip_path.stat().st_size} bytes")
    if not args.verify:
        (args.out / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
        (args.out / "catalog.json").write_text(CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
    print("Module packages verified.")


if __name__ == "__main__":
    main()
