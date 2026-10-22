"""Boundary tests only: synthetic readbacks never establish a real Notion build."""

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, ClassVar, cast
from uuid import uuid4

import pytest
from notion_client import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import money_machine.application.real_notion_build as module
from money_machine.application.real_draft_authority import DraftRunAuthority, DraftRunRefused
from money_machine.application.real_draft_effects import DraftEffectUncertain
from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.product_spec import ColourToken, Hub, ProductSpec


class Adapter:
    objects: ClassVar[dict[str, Any]] = {}
    children: ClassVar[dict[str, Any]] = {}
    writes = 0
    corrupt: ClassVar[str | None] = None

    def __init__(self, authority, **kwargs):
        self.authority = authority

    @staticmethod
    def _page_title(page):
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                return "".join(
                    x.get("plain_text", x.get("text", {}).get("content", ""))
                    for x in prop.get("title", [])
                )
        return ""

    @classmethod
    def put(cls, obj, parent: str | None = None):
        obj = deepcopy(obj)
        obj["id"] = str(uuid4())
        cls.objects[obj["id"]] = obj
        cls.children.setdefault(parent or "workspace", []).append(obj["id"])
        cls.writes += 1
        return deepcopy(obj)

    async def create_workspace_product(self, title, *, children):
        return self.put(
            {
                "properties": {"title": {"type": "title", **module.title(title)}},
                "parent": {"type": "workspace"},
                "blocks": children,
            }
        )

    async def get_workspace_product(self, identity, title, marker):
        return deepcopy(self.objects[identity])

    async def find_workspace_product(self, title, marker):
        return next(
            (
                deepcopy(p)
                for p in self.objects.values()
                if p.get("parent", {}).get("type") == "workspace" and self._page_title(p) == title
            ),
            None,
        )

    async def get_page(self, identity):
        return deepcopy(self.objects[identity])

    async def create_page(self, parent, title, *, children, icon, cover=None):
        return self.put(
            {
                "properties": {"title": {"type": "title", **module.title(title)}},
                "parent": {"page_id": parent},
                "blocks": children,
                "icon": icon,
                "cover": cover,
            },
            parent,
        )

    async def find_page(self, parent, title):
        return next(
            (
                deepcopy(self.objects[i])
                for i in self.children.get(parent, [])
                if self._page_title(self.objects[i]) == title
            ),
            None,
        )

    async def list_blocks(self, parent):
        blocks = deepcopy(self.objects[parent].get("blocks", []))
        for identity in self.children.get(parent, []):
            obj = self.objects[identity]
            if "db_title" in obj or "view_page" in obj:
                blocks.append({"id": identity, "type": "child_database"})
            elif "properties" in obj and "title" in obj["properties"]:
                blocks.append({"id": identity, "type": "child_page"})
        return blocks

    async def append_blocks(self, parent, children):
        result = []
        for child in children:
            child = deepcopy(child)
            child["id"] = str(uuid4())
            result.append(child)
        self.objects[parent].setdefault("blocks", []).extend(result)
        type(self).writes += 1
        return {"results": deepcopy(result)}

    async def create_database(self, parent, title, properties):
        ds = self.put(
            {
                "properties": {
                    k: {"id": k, "type": next(iter(v)), **v} for k, v in properties.items()
                }
            }
        )
        return self.put(
            {"db_title": title, "parent": {"page_id": parent}, "data_sources": [{"id": ds["id"]}]},
            parent,
        )

    async def find_database(self, parent, title):
        return next(
            (
                deepcopy(self.objects[i])
                for i in self.children.get(parent, [])
                if self.objects[i].get("db_title") == title
            ),
            None,
        )

    async def get_database(self, identity):
        return deepcopy(self.objects[identity])

    async def get_data_source(self, identity):
        obj = deepcopy(self.objects[identity])
        if type(self).corrupt == "schema":
            obj["properties"].pop(next(iter(obj["properties"])))
        for prop in obj["properties"].values():
            kind = prop.get("type")
            if type(self).corrupt == "select_options" and kind == "select":
                prop["select"]["options"] = []
            if type(self).corrupt == "number_format" and kind == "number":
                prop["number"]["format"] = "percent"
        return obj

    async def create_row(self, source, properties):
        return self.put(
            {
                "properties": {k: {"type": next(iter(v)), **v} for k, v in properties.items()},
                "parent": {"data_source_id": source},
            },
            source,
        )

    async def query_rows(self, source):
        rows = [deepcopy(self.objects[i]) for i in self.children.get(source, [])]
        schema = self.objects[source].get("properties", {})
        for row in rows:
            for name, prop in schema.items():
                if prop.get("type") == "formula":
                    row["properties"][name] = {"formula": {"type": "number", "number": 0}}
            if "Water goal" in row["properties"]:
                row["properties"]["Notification"] = {
                    "formula": {"type": "string", "string": "Synthetic boundary result"}
                }
                for k in ("Open tasks", "Birthdays", "Spending", "Water logged"):
                    row["properties"][k] = {"rollup": {"type": "number", "number": 0}}
                if type(self).corrupt == "formula":
                    row["properties"]["Notification"] = {"formula": {"type": "error"}}
                if type(self).corrupt == "rollup":
                    row["properties"]["Spending"]["rollup"]["number"] = 99
                if type(self).corrupt == "duplicate":
                    rows.append(deepcopy(row))
                    break
        return rows

    async def create_linked_view(self, page, source, name, *, filter, view_type):
        return self.put(
            {
                "name": name,
                "data_source_id": source,
                "type": view_type,
                "filter": filter,
                "view_page": page,
                "parent": {"page_id": page},
                "configuration": {
                    "type": "calendar",
                    "date_property_id": self.objects[source]["properties"]["Date"]["id"],
                    "view_range": "month",
                }
                if view_type == "calendar"
                else None,
            },
            page,
        )

    async def get_view(self, identity):
        obj = deepcopy(self.objects[identity])
        if type(self).corrupt == "view":
            obj["data_source_id"] = str(uuid4())
        if type(self).corrupt == "calendar" and obj.get("type") == "calendar":
            obj["configuration"]["date_property_id"] = "wrong-date-property"
        return obj

    async def find_linked_view(self, page, source, name):
        return next(
            (
                deepcopy(self.objects[i])
                for i in self.children.get(page, [])
                if self.objects[i].get("data_source_id") == source
                and self.objects[i].get("name") == name
            ),
            None,
        )


class Effects:
    ledger: ClassVar[dict[str, str]] = {}
    uncertain = False

    def __init__(self, *args, **kwargs):
        pass

    async def assert_lease(self):
        pass

    async def execute(self, key, *, create, reconcile, **kwargs):
        if type(self).uncertain:
            raise DraftEffectUncertain("synthetic pending effect")
        known = self.ledger.get(key)
        observed = await reconcile(known)
        if observed is None:
            if known:
                raise DraftEffectUncertain("pending result missing")
            result = await create()
            self.ledger[key] = result["id"]
            observed = await reconcile(result["id"])
        return observed


@pytest.fixture
def inputs(monkeypatch):
    Adapter.objects, Adapter.children, Adapter.writes, Adapter.corrupt = {}, {}, 0, None
    Effects.ledger, Effects.uncertain = {}, False
    monkeypatch.setattr(module, "RealPrivateNotionAdapter", Adapter)
    monkeypatch.setattr(module, "SqlDraftEffects", Effects)
    product = uuid4()
    workspace = uuid4()
    spec = ProductSpec(
        spec_id=uuid4(),
        product_id=product,
        workflow_id=uuid4(),
        version=1,
        producing_job_id=uuid4(),
        producing_agent_run_id=uuid4(),
        identity="Planner",
        base_category="Notion Planner",
        buyer_problem="Keep everyday life organised.",
        title="Quietly Built Money and Life Planner",
        tier="low-ticket",
        real_price=Decimal("7.50"),
        anchor_price=Decimal("7.50"),
        currency="GBP",
        palette_name="Quietly Built",
        palette_tokens=tuple(
            ColourToken(name=n, hex=c)
            for n, c in (("Forest", "#2F5D50"), ("Sand", "#C8B89D"), ("Slate", "#64748B"))
        ),
        hubs=tuple(
            Hub(name=n, description="Useful connected planning.", page_count=3)
            for n in ("Daily Plan", "Calendar", "Routines", "Money", "Meals", "Notes and Reviews")
        ),
        colour_variants=("Forest", "Sand", "Slate"),
        flagship_feature="Connected notification",
        shared_databases=module.SOURCES,
        page_target_min=25,
        page_target_max=100,
        experiment_hypothesis="A testable hypothesis.",
        concept_fingerprint="a" * 64,
        rule_version="product-rules-v1",
        evidence=(
            EvidenceReference(
                evidence_id=uuid4(),
                evidence_type="TEST_ONLY",
                source_reference="test",
                observed_at=datetime.now(UTC),
                sha256="b" * 64,
                safe_summary="Boundary only",
            ),
        ),
        created_at=datetime(2026, 10, 21, tzinfo=UTC),
    )
    authority = DraftRunAuthority(
        run_id="test-real-1", product_id=product, verified_notion_parent_id=workspace
    )
    builder = module.RealNotionProductBuilder(
        authority,
        sdk=cast(AsyncClient, object()),
        session_factory=cast(async_sessionmaker[AsyncSession], object()),
        job_id=uuid4(),
        lease_owner="test",
        cover_urls={name: f"https://assets.example/{name.lower()}.png" for name in module.THEMES},
    )
    return builder, spec, workspace


async def build(inputs):
    builder, spec, workspace = inputs
    return await builder.build(spec, run_id="test-real-1", workspace_id=workspace)


@pytest.mark.asyncio
async def test_three_complete_variants_shared_hub_sources_and_notification(inputs):
    manifest = await build(inputs)
    assert len(manifest["variants"]) == 3
    assert len({v["root_id"] for v in manifest["variants"]}) == 3
    assert (
        len({s["data_source_id"] for v in manifest["variants"] for s in v["sources"].values()})
        == 18
    )
    for variant in manifest["variants"]:
        assert len(variant["sources"]) == 6
        assert len(variant["hubs"]) == 6
        assert len(variant["home_view_ids"]) == 3
        assert len({i for h in variant["hubs"] for i in h["guide_ids"]}) == 12
        for hub in variant["hubs"]:
            assert len(hub["view_ids"]) == 2
            assert hub["source_id"] in {s["data_source_id"] for s in variant["sources"].values()}
        ds = Adapter.objects[variant["notification"]["data_source_id"]]
        for source in ("Tasks", "Events", "Finance", "Habits"):
            assert (
                ds["properties"][source]["relation"]["data_source_id"]
                == variant["sources"][source]["data_source_id"]
            )
        expr = ds["properties"]["Notification"]["formula"]["expression"]
        assert 'prop("Open tasks")' in expr and 'prop("Spending")' in expr and "now()" in expr
        row = Adapter.objects[variant["notification"]["row_id"]]
        assert all(
            row["properties"][name]["relation"] for name in ("Tasks", "Events", "Finance", "Habits")
        )
    assert manifest["visual_review"].startswith("pending")


@pytest.mark.asyncio
async def test_replay_adopts_same_ids_without_provider_post(inputs):
    first = await build(inputs)
    count = Adapter.writes
    assert await build(inputs) == first
    assert Adapter.writes == count


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "corrupt",
    [
        "schema",
        "formula",
        "duplicate",
        "view",
        "rollup",
        "calendar",
        "select_options",
        "number_format",
    ],
)
async def test_wrong_provider_readback_refused(inputs, corrupt):
    Adapter.corrupt = corrupt
    with pytest.raises(DraftRunRefused):
        await build(inputs)


@pytest.mark.asyncio
async def test_uncertain_effect_propagates_without_creating(inputs):
    Effects.uncertain = True
    with pytest.raises(DraftEffectUncertain):
        await build(inputs)
    assert Adapter.writes == 0


@pytest.mark.asyncio
async def test_scope_refused_before_any_effect(inputs):
    builder, spec, workspace = inputs
    with pytest.raises(DraftRunRefused):
        await builder.build(spec, run_id="other-run", workspace_id=workspace)
    assert Adapter.writes == 0


@pytest.mark.asyncio
async def test_variant_covers_and_backlinks_are_read_back_and_replay_safe(inputs):
    manifest = await build(inputs)
    for variant in manifest["variants"]:
        home = variant["root_id"]
        expected_cover = {
            "type": "external",
            "external": {"url": f"https://assets.example/{variant['name'].lower()}.png"},
        }
        for page_id in [home, *(h["page_id"] for h in variant["hubs"])]:
            assert Adapter.objects[page_id]["cover"] == expected_cover
        for hub in variant["hubs"]:
            links = [
                b["link_to_page"]["page_id"]
                for b in Adapter.objects[hub["page_id"]]["blocks"]
                if b.get("type") == "link_to_page"
            ]
            assert links == [home]
            for guide_id in hub["guide_ids"]:
                links = [
                    b["link_to_page"]["page_id"]
                    for b in Adapter.objects[guide_id]["blocks"]
                    if b.get("type") == "link_to_page"
                ]
                assert links == [hub["page_id"], home]
    before = Adapter.writes
    assert await build(inputs) == manifest
    assert Adapter.writes == before


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["cover", "icon", "backlink", "duplicate_backlink"])
async def test_cover_or_backlink_drift_stops_without_mutation(inputs, drift):
    manifest = await build(inputs)
    hub = Adapter.objects[manifest["variants"][0]["hubs"][0]["page_id"]]
    if drift in ("cover", "icon"):
        hub[drift] = None
    else:
        link = next((b for b in hub["blocks"] if b.get("type") == "link_to_page"), None)
        assert link is not None
        if drift == "backlink":
            link["link_to_page"]["page_id"] = str(uuid4())
        else:
            hub["blocks"].append(deepcopy(link))
    before = Adapter.writes
    with pytest.raises(DraftRunRefused):
        await build(inputs)
    assert Adapter.writes == before


@pytest.mark.asyncio
async def test_counts_are_observed_including_linked_containers_and_extra_child(inputs):
    first = await build(inputs)
    variant = first["variants"][0]
    assert variant["regular_page_count"] == 19
    assert variant["database_container_count"] == 23  # 7 sources + 16 linked views
    assert variant["page_count_including_databases"] == 42
    assert len(variant["page_inventory"]["page_ids"]) == 19
    extra = await inputs[0].adapter.create_page(
        variant["hubs"][0]["page_id"], "Extra guide", children=[], icon=None
    )
    before = Adapter.writes
    second = await build(inputs)
    observed = second["variants"][0]
    assert observed["regular_page_count"] == 20
    assert observed["page_count_including_databases"] == 43
    assert extra["id"] in observed["page_inventory"]["page_ids"]
    assert Adapter.writes == before


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["cycle", "wrong_parent", "nested"])
async def test_inventory_refuses_incomplete_or_invalid_readback(inputs, damage):
    first = await build(inputs)
    home = first["variants"][0]["root_id"]
    if damage == "cycle":
        Adapter.objects[home]["blocks"].append({"type": "child_page", "id": home})
    elif damage == "wrong_parent":
        identity = first["variants"][0]["hubs"][0]["guide_ids"][0]
        Adapter.objects[identity]["parent"]["page_id"] = home
    else:
        Adapter.objects[home]["blocks"].append({"type": "toggle", "has_children": True})
    before = Adapter.writes
    with pytest.raises(DraftRunRefused):
        await build(inputs)
    assert Adapter.writes == before


@pytest.mark.asyncio
@pytest.mark.parametrize("covers", [None, {}, {"Forest": "fixture://palette/Forest/#2F5D50"}])
async def test_missing_cover_assets_refused_before_effects(inputs, covers):
    inputs[0].cover_urls = covers
    with pytest.raises(DraftRunRefused, match="cover"):
        await build(inputs)
    assert Adapter.writes == 0


@pytest.mark.asyncio
async def test_incomplete_child_inventory_cannot_claim_complete_build(inputs, monkeypatch):
    first = await build(inputs)
    home = first["variants"][0]["root_id"]
    missing = first["variants"][0]["hubs"][0]["page_id"]
    original = Adapter.list_blocks

    async def incomplete(self, identity):
        children = await original(self, identity)
        return [b for b in children if b.get("id") != missing] if identity == home else children

    monkeypatch.setattr(Adapter, "list_blocks", incomplete)
    before = Adapter.writes
    with pytest.raises(DraftRunRefused, match="inventory_missing"):
        await build(inputs)
    assert Adapter.writes == before


@pytest.mark.asyncio
async def test_linked_containers_do_not_inflate_spec_content_target(inputs):
    first = await build(inputs)
    assert first["variants"][0]["content_page_count_including_source_databases"] == 26
    inputs = (inputs[0], inputs[1].model_copy(update={"page_target_min": 40}), inputs[2])
    before = Adapter.writes
    with pytest.raises(DraftRunRefused, match="outside_spec_target"):
        await build(inputs)
    assert Adapter.writes == before
