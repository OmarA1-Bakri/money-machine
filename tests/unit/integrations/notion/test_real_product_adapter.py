"""Mock-transport boundary tests; none of these establish provider delivery."""

import json
from typing import Any, cast
from uuid import UUID

import httpx
import pytest
from notion_client import AsyncClient

from money_machine.application.real_draft_authority import DraftRunAuthority, DraftRunRefused
from money_machine.integrations.notion.real_product_adapter import (
    NotionEffectUncertain,
    RealPrivateNotionAdapter,
)


async def approve_test_write():
    return None


ROOT = "11111111-1111-4111-8111-111111111111"
PAGE = "22222222-2222-4222-8222-222222222222"
DATABASE = "33333333-3333-4333-8333-333333333333"
SOURCE = "44444444-4444-4444-8444-444444444444"
VIEW = "55555555-5555-4555-8555-555555555555"
OUTSIDE = "66666666-6666-4666-8666-666666666666"


def resource(oid, parent_type, parent_id=None):
    parent = {"type": parent_type, parent_type: parent_id or True}
    return {"id": oid, "parent": parent, "archived": False, "public_url": None}


@pytest.fixture
async def setup_adapter():
    calls = []
    objects = {
        f"pages/{ROOT}": resource(ROOT, "workspace"),
        f"pages/{PAGE}": resource(PAGE, "page_id", ROOT),
        f"databases/{DATABASE}": resource(DATABASE, "page_id", PAGE),
        f"data_sources/{SOURCE}": resource(SOURCE, "database_id", DATABASE),
        f"views/{VIEW}": resource(VIEW, "database_id", DATABASE),
        f"pages/{OUTSIDE}": resource(OUTSIDE, "workspace"),
    }
    state: dict[str, Any] = {"failure": None, "workspace": ROOT, "owner": "user"}

    def handler(request):
        path = request.url.path.removeprefix("/v1/")
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, path, body, dict(request.url.params)))
        assert request.headers["Notion-Version"] == "2025-09-03"
        if request.method == "GET" and path == "users/me":
            return httpx.Response(
                200,
                json={
                    "bot": {
                        "workspace_id": state["workspace"],
                        "owner": {"type": state["owner"]},
                    }
                },
            )
        if request.method == "GET" and path in objects:
            return httpx.Response(200, json=objects[path])
        if request.method == "POST" and path == "search":
            return httpx.Response(
                200, json={"results": state.get("search_results", []), "has_more": False}
            )
        if request.method == "GET" and path in state.get("custom_blocks", {}):
            return httpx.Response(
                200, json={"results": state["custom_blocks"][path], "has_more": False}
            )
        if request.method == "GET" and path.endswith("/children"):
            if "start_cursor" in request.url.params:
                return httpx.Response(200, json={"results": [{"id": PAGE}], "has_more": False})
            return httpx.Response(
                200,
                json={
                    "results": [{"id": DATABASE}],
                    "has_more": True,
                    "next_cursor": "cursor1",
                },
            )
        if path.endswith("/query"):
            return httpx.Response(200, json={"results": [{"id": PAGE}], "has_more": False})
        if state["failure"] == "lost_response":
            raise httpx.ReadTimeout("accepted effect; response lost", request=request)
        if state["failure"] == "invalid_response":
            return httpx.Response(200, json={})
        if state["failure"] == "server_error":
            return httpx.Response(503, json={"code": "service_unavailable", "message": "private"})
        if path.endswith("/children"):
            return httpx.Response(200, json={"results": [{"id": PAGE}]})
        return httpx.Response(200, json={"id": VIEW if path == "views" else PAGE})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        sdk = AsyncClient(auth="fixture-only-not-real", notion_version="2025-09-03", client=http)
        authority = DraftRunAuthority(
            run_id="test-real-boundary",
            product_id=UUID(PAGE),
            verified_notion_parent_id=UUID(ROOT),
        )
        yield (
            RealPrivateNotionAdapter(authority, sdk=sdk, before_write=approve_test_write),
            calls,
            objects,
            state,
            sdk,
        )


@pytest.mark.asyncio
async def test_create_database_uses_initial_data_source_after_actual_ancestry(setup_adapter):
    adapter, calls, _, _, _ = setup_adapter
    properties = {"Name": {"title": {}}, "Remaining": {"formula": {"expression": "1 + 1"}}}
    await adapter.create_database(PAGE, "Tasks", properties)
    assert [(c[0], c[1]) for c in calls[:-1]] == [
        ("GET", f"pages/{PAGE}"),
        ("GET", f"pages/{ROOT}"),
    ]
    assert calls[-1][2]["initial_data_source"] == {"properties": properties}
    assert PAGE in adapter.created_ids


@pytest.mark.asyncio
async def test_outside_parent_refused_without_mutation(setup_adapter):
    adapter, calls, _, _, _ = setup_adapter
    with pytest.raises(DraftRunRefused, match="outside_verified_parent"):
        await adapter.create_page(OUTSIDE, "No")
    assert all(c[0] == "GET" for c in calls)


@pytest.mark.asyncio
async def test_public_ancestor_refused_even_if_child_private(setup_adapter):
    adapter, calls, objects, _, _ = setup_adapter
    objects[f"pages/{ROOT}"]["public_url"] = "https://public.example"
    with pytest.raises(DraftRunRefused, match="private_active"):
        await adapter.create_row(SOURCE, {"Name": {"title": []}})
    assert all(c[0] == "GET" for c in calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["lost_response", "server_error", "invalid_response"])
async def test_uncertain_mutation_has_one_attempt_and_no_retry(setup_adapter, failure):
    adapter, calls, _, state, _ = setup_adapter
    state["failure"] = failure
    with pytest.raises(NotionEffectUncertain):
        await adapter.create_page(ROOT, "Unique durable-intent title")
    assert sum(c[0] == "POST" for c in calls) == 1


@pytest.mark.asyncio
async def test_linked_view_has_real_fixed_view_endpoint_and_scoped_source(setup_adapter):
    adapter, calls, _, _, _ = setup_adapter
    selected = {"property": "Status", "select": {"equals": "Active"}}
    await adapter.create_linked_view(PAGE, SOURCE, "Active", filter=selected)
    assert calls[-1][:2] == ("POST", "views")
    assert calls[-1][2] == {
        "create_database": {
            "parent": {"type": "page_id", "page_id": PAGE},
            "show_data_source_title": False,
        },
        "data_source_id": SOURCE,
        "name": "Active",
        "type": "table",
        "filter": selected,
    }
    assert await adapter.get_view(VIEW)


@pytest.mark.asyncio
async def test_cross_product_relation_and_public_control_refused(setup_adapter):
    adapter, calls, _, _, _ = setup_adapter
    with pytest.raises(DraftRunRefused):
        await adapter.create_row(SOURCE, {"Peer": {"relation": [{"id": OUTSIDE}]}})
    with pytest.raises(DraftRunRefused, match="forbidden_control"):
        await adapter.append_blocks(PAGE, [{"public": True}])
    with pytest.raises(DraftRunRefused, match="external_resource"):
        await adapter.append_blocks(PAGE, [{"image": {"external": {"url": "https://example.com"}}}])
    assert all(c[0] == "GET" for c in calls)


@pytest.mark.asyncio
async def test_workspace_create_requires_verified_owner_and_bound_workspace(setup_adapter):
    adapter, calls, _, _, sdk = setup_adapter
    with pytest.raises(DraftRunRefused, match="workspace_creation"):
        await adapter.create_workspace_product("Root")
    scoped = RealPrivateNotionAdapter(
        adapter.authority, sdk=sdk, before_write=approve_test_write, verified_workspace_id=ROOT
    )
    await scoped.create_workspace_product("Root")
    assert calls[-2][1] == "users/me"
    assert calls[-1][2]["parent"] == {"workspace": True}


@pytest.mark.asyncio
async def test_pagination_preserves_all_results_and_readonly_query(setup_adapter):
    adapter, calls, _, _, _ = setup_adapter
    assert await adapter.list_blocks(ROOT) == [{"id": DATABASE}, {"id": PAGE}]
    assert calls[-1][3]["start_cursor"] == "cursor1"
    assert await adapter.query_rows(SOURCE) == [{"id": PAGE}]
    assert calls[-1][1] == f"data_sources/{SOURCE}/query"
    assert adapter.created_ids == set()


def test_mode_is_explicit_and_no_public_or_delete_methods(setup_adapter):
    assert not hasattr(RealPrivateNotionAdapter, "publish")
    assert not hasattr(RealPrivateNotionAdapter, "delete")
    authority = DraftRunAuthority(run_id="test", product_id=UUID(PAGE))
    with pytest.raises(DraftRunRefused):
        RealPrivateNotionAdapter(authority, sdk=cast(AsyncClient, None), mode="simulation")


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("workspace", OUTSIDE), ("owner", "workspace")])
async def test_workspace_identity_owner_mismatch_cannot_create(setup_adapter, field, value):
    adapter, calls, _, state, sdk = setup_adapter
    state[field] = value
    scoped = RealPrivateNotionAdapter(
        adapter.authority, sdk=sdk, before_write=approve_test_write, verified_workspace_id=ROOT
    )
    with pytest.raises(DraftRunRefused, match="workspace_owner_mismatch"):
        await scoped.create_workspace_product("Forbidden root")
    assert [c[0] for c in calls] == ["GET"]


@pytest.mark.asyncio
async def test_schema_supports_formula_and_scoped_relations_without_deletion(setup_adapter):
    adapter, calls, _, _, _ = setup_adapter
    schema = {
        "Total": {"formula": {"expression": 'prop("Hours") * prop("Rate")'}},
        "Tasks": {"relation": {"data_source_id": SOURCE, "single_property": {}}},
    }
    await adapter.update_data_source(SOURCE, schema)
    assert calls[-1][:3] == ("PATCH", f"data_sources/{SOURCE}", {"properties": schema})
    mutations = len([c for c in calls if c[0] == "PATCH"])
    with pytest.raises(DraftRunRefused, match="deletion_forbidden"):
        await adapter.update_data_source(SOURCE, {"Total": None})
    assert len([c for c in calls if c[0] == "PATCH"]) == mutations


@pytest.mark.asyncio
async def test_ancestry_is_not_cached_after_parent_moves(setup_adapter):
    adapter, calls, objects, _, _ = setup_adapter
    await adapter.get_page(PAGE)
    objects[f"pages/{PAGE}"]["parent"] = {"type": "page_id", "page_id": OUTSIDE}
    with pytest.raises(DraftRunRefused, match="outside_verified_parent"):
        await adapter.append_blocks(PAGE, [{"object": "block", "type": "divider", "divider": {}}])
    assert all(c[0] == "GET" for c in calls)


@pytest.mark.asyncio
async def test_authority_called_for_every_wire_operation(setup_adapter, monkeypatch):
    adapter, calls, _, _, _ = setup_adapter
    observed = []
    real_authorize = DraftRunAuthority.authorize

    def authorize(self, operation, **kwargs):
        observed.append((operation, kwargs))
        return real_authorize(self, operation, **kwargs)

    monkeypatch.setattr(DraftRunAuthority, "authorize", authorize)
    await adapter.create_page(PAGE, "Bounded")
    assert len(observed) == len(calls)
    assert observed[-1][0] == "notion.private_product.write"
    assert all(item[1]["notion_parent_id"] == UUID(ROOT) for item in observed)


@pytest.mark.asyncio
async def test_workspace_reconciliation_requires_marker_and_private_workspace_parent(setup_adapter):
    old, _calls, objects, state, sdk = setup_adapter
    adapter = RealPrivateNotionAdapter(
        old.authority, sdk=sdk, before_write=approve_test_write, verified_workspace_id=ROOT
    )
    page = {
        **resource(PAGE, "workspace"),
        "properties": {"title": {"type": "title", "title": [{"plain_text": "Exact run title"}]}},
    }
    objects[f"pages/{PAGE}"] = page
    state["search_results"] = [page]
    state["custom_blocks"] = {
        f"blocks/{PAGE}/children": [
            {
                "id": PAGE,
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "other marker"}]},
            }
        ]
    }
    assert await adapter.find_workspace_product("Exact run title", "expected-marker") is None
    state["custom_blocks"][f"blocks/{PAGE}/children"][0]["paragraph"]["rich_text"][0][
        "plain_text"
    ] = "expected-marker"
    found = await adapter.find_workspace_product("Exact run title", "expected-marker")
    assert found is not None
    assert found["id"] == PAGE
    objects[f"pages/{PAGE}"]["public_url"] = "https://public.invalid"
    with pytest.raises(DraftRunRefused):
        await adapter.get_workspace_product(PAGE, "Exact run title", "expected-marker")


@pytest.mark.asyncio
async def test_child_page_reconciliation_checks_direct_parent(setup_adapter):
    adapter, _, objects, state, _ = setup_adapter
    state["custom_blocks"] = {
        f"blocks/{ROOT}/children": [
            {"id": PAGE, "type": "child_page", "child_page": {"title": "Own child"}}
        ]
    }
    objects[f"pages/{PAGE}"]["properties"] = {
        "title": {"type": "title", "title": [{"plain_text": "Own child"}]}
    }
    assert (await adapter.find_page(ROOT, "Own child"))["id"] == PAGE
    objects[f"pages/{PAGE}"]["parent"] = {"type": "workspace", "workspace": True}
    with pytest.raises(DraftRunRefused):
        await adapter.find_page(ROOT, "Own child")


@pytest.mark.asyncio
async def test_write_requires_durable_guard_even_with_valid_ancestry(setup_adapter):
    adapter, calls, _, _, sdk = setup_adapter
    unguarded = RealPrivateNotionAdapter(adapter.authority, sdk=sdk)
    with pytest.raises(DraftRunRefused, match="durable_effect_guard_required"):
        await unguarded.create_page(ROOT, "Forbidden unguarded write")
    assert not any(method == "POST" for method, _, _, _ in calls)


@pytest.mark.asyncio
async def test_write_guard_revocation_after_ancestry_prevents_post(setup_adapter):
    adapter, calls, _, _, sdk = setup_adapter

    async def revoked():
        raise RuntimeError("sensitive failure text not emitted")

    guarded = RealPrivateNotionAdapter(adapter.authority, sdk=sdk, before_write=revoked)
    with pytest.raises(DraftRunRefused, match="durable_effect_guard_refused") as error:
        await guarded.create_page(ROOT, "Must not be created")
    assert "sensitive failure" not in str(error.value)
    assert any(method == "GET" for method, _, _, _ in calls)
    assert not any(method == "POST" for method, _, _, _ in calls)


@pytest.mark.asyncio
async def test_calendar_uses_verified_date_property_configuration(setup_adapter):
    adapter, calls, objects, _, _ = setup_adapter
    objects[f"data_sources/{SOURCE}"]["properties"] = {
        "Date": {"id": "actual-date-id", "type": "date", "date": {}}
    }
    await adapter.create_linked_view(PAGE, SOURCE, "Monthly calendar", view_type="calendar")
    sent = calls[-1][2]
    assert sent["configuration"] == {
        "type": "calendar",
        "date_property_id": "actual-date-id",
        "view_range": "month",
    }
    assert sent["create_database"]["show_data_source_title"] is False


@pytest.mark.asyncio
async def test_page_cover_uses_supported_external_file_shape(setup_adapter):
    adapter, calls, _, _, _ = setup_adapter
    cover = {"type": "external", "external": {"url": "https://assets.example/forest.png"}}
    await adapter.create_page(PAGE, "Forest", cover=cover)
    assert calls[-1][2]["cover"] == cover
    assert calls[-1][:2] == ("POST", "pages")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "fixture://palette/Forest",
        "http://assets.example/a.png",
        "https://user:pass@assets.example/a.png",
        "https://assets.example/a.png?token=secret",
        "https://assets.example/a.png#fragment",
        "https://localhost/a.png",
        "https://127.0.0.1/a.png",
        "https://assets.example:443/a.png",
        "https://assets.example/a.html",
    ],
)
async def test_unsupported_cover_refused_without_write(setup_adapter, url):
    adapter, calls, _, _, _ = setup_adapter
    with pytest.raises(DraftRunRefused, match="cover"):
        await adapter.create_page(
            PAGE, "Forest", cover={"type": "external", "external": {"url": url}}
        )
    assert all(c[0] == "GET" for c in calls)


@pytest.mark.asyncio
async def test_cover_exception_does_not_enable_external_block_resources(setup_adapter):
    adapter, calls, _, _, _ = setup_adapter
    with pytest.raises(DraftRunRefused, match="external_resource_forbidden"):
        await adapter.create_page(
            PAGE,
            "Forest",
            children=[
                {
                    "type": "image",
                    "image": {
                        "type": "external",
                        "external": {"url": "https://assets.example/forest.png"},
                    },
                }
            ],
        )
    assert all(c[0] == "GET" for c in calls)
