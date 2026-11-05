#!/usr/bin/env python3
"""Publish isolated download/<module> branches from the approved module catalog.

Run only from the trusted main branch in GitHub Actions.
Each download branch has only that module's files and a generated README.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from package_modules import ROOT, module_catalog, module_files


def github_api(repository: str, endpoint: str, token: str, method="GET", payload=None):
    url = f"https://api.github.com/repos/{repository}/{endpoint}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "open-hvac-module-publisher",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 404 and method == "GET":
            return None
        raise RuntimeError(f"GitHub API error {exc.code} at {endpoint}") from exc


def distribution_readme(module: dict, source_sha: str, repo: str) -> str:
    return (
        f"# {module['name']}\n\n"
        f"**Open HVAC / OpenLVI Bridge — isolated module download**\n\n"
        f"{module['summary']}\n\n"
        f"**Validation:** {module['status']}  \n"
        f"**Module:** {module['slug']}  \n"
        f"**Source commit:** {source_sha}\n\n"
        f"## Install\n\n"
        f"Download this branch as a ZIP, extract it, and follow the module's\n"
        f"[full installation guide](https://github.com/{repo}/blob/main/{module['documentation']}).\n"
        f"This is a source snapshot; do not install unrelated files or assume\n"
        f"that simulation testing proves physical device compatibility.\n\n"
        f"**Destination:** {module['target']}\n\n"
        f"## Safety\n\n{module['caution']}\n\n"
        f"Contribute in [main](https://github.com/{repo}/tree/main), not in a\n"
        f"download branch. The download branches are regenerated from main.\n\n"
        f"Independent MIT-licensed community project, not manufacturer-endorsed.\n"
    )


def publish(repository: str, token: str) -> None:
    if not token:
        raise RuntimeError("GH_TOKEN required; no branch changes performed")
    current_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    source = github_api(repository, "git/ref/heads/main", token)
    source_sha = source["object"]["sha"]
    if source_sha != current_sha:
        raise RuntimeError("Checkout is not at the current main head; refusing to publish")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    for module in module_catalog():
        branch = f"download/{module['slug']}"
        ref = github_api(repository, f"git/ref/heads/{quote(branch, safe='/')}", token)
        parent = ref["object"]["sha"] if ref else current_sha
        tree_items = [
            {"path": "README.md", "mode": "100644", "type": "blob",
             "content": distribution_readme(module, current_sha, repository)},
            {"path": "LICENSE", "mode": "100644", "type": "blob",
             "content": license_text},
        ]
        for path in module_files(module):
            relative = path.relative_to(ROOT).as_posix()
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                raise ValueError(f"Non-text file needs an explicit publishing review: {relative}")
            tree_items.append(
                {"path": relative, "mode": "100644", "type": "blob", "content": content}
            )
        tree = github_api(repository, "git/trees", token, "POST", {"tree": tree_items})
        commit = github_api(
            repository, "git/commits", token, "POST",
            {"message": f"Sync {branch} from main {current_sha[:12]}",
             "tree": tree["sha"], "parents": [parent]}
        )
        if ref:
            github_api(
                repository, f"git/refs/heads/{quote(branch, safe='/')}",
                token, "PATCH", {"sha": commit["sha"], "force": False}
            )
        else:
            github_api(
                repository, "git/refs", token, "POST",
                {"ref": f"refs/heads/{branch}", "sha": commit["sha"]}
            )
        print(f"Updated {branch} ({len(tree_items) - 2} files)")


if __name__ == "__main__":
    if os.environ.get("GITHUB_REPOSITORY", "") != "artepe/Open-HVACBridge-homeassistant":
        sys.exit("Refusing to publish outside the configured Open HVAC repository")
    publish(os.environ["GITHUB_REPOSITORY"], os.environ.get("GH_TOKEN", ""))
