"""Prepare a draft-only scope; never authenticate, mutate, or assert provider delivery."""

from __future__ import annotations

import argparse
import json
from uuid import UUID

from pydantic import ValidationError

from money_machine.application.real_draft_authority import DraftRunAuthority


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--verified-shop-id", type=int)
    parser.add_argument("--notion-parent-id")
    args = parser.parse_args(argv)
    try:
        authority = DraftRunAuthority(
            run_id=args.run_id,
            product_id=UUID(args.product_id),
            verified_shop_id=args.verified_shop_id,
            verified_notion_parent_id=UUID(args.notion_parent_id)
            if args.notion_parent_id
            else None,
        )
        authority.authorize("local.qa", run_id=authority.run_id, product_id=authority.product_id)
    except (ValueError, ValidationError):
        parser.exit(2, "invalid draft scope; no effects performed\n")
    blockers = []
    if authority.verified_notion_parent_id is None:
        blockers.append("NOTION_PARENT_UNVERIFIED")
    if authority.verified_shop_id is None:
        blockers.append("ETSY_NUMERIC_SHOP_ID_UNVERIFIED")
    print(
        json.dumps(
            {
                "run_id": authority.run_id,
                "authority": authority.model_dump(mode="json"),
                "provider_verification_performed": False,
                "effects_performed": False,
                "publishing_enabled": False,
                "spending_enabled": False,
                "blockers": blockers,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
