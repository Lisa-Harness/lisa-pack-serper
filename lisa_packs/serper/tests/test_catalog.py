from __future__ import annotations

import json

from sdk.content._catalog import build_tool_catalog_json, resolve_tool_roots

from lisa_packs.serper import get_content_root


def test_serper_pack_serper_search_tool_discovered() -> None:
    roots = resolve_tool_roots([get_content_root()])
    assert roots, "No tools/ directory found in serper provider pack"

    catalog = json.loads(build_tool_catalog_json(roots))

    assert "serper_search" in catalog
    tool = catalog["serper_search"]
    assert tool["tool_id"] == "serper_search"
    assert tool["module_path"].startswith("lisa_packs.serper.tools.")