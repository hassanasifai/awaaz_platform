"""Seed a fresh dev DB with one org + one store + one customer + one order.

Run from inside the api container:
    python -m awaaz_api.scripts.seed_dev
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import text

from awaaz_api.observability import configure_logging, get_logger
from awaaz_api.persistence import AsyncSessionLocal, set_tenant_context

_log = get_logger("awaaz.seed")


async def main() -> None:
    configure_logging()
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(session, bypass=True)
            org_id = (
                await session.execute(
                    text(
                        """
                        INSERT INTO organizations (slug, name)
                        VALUES ('demo', 'Demo Org')
                        ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
                        RETURNING id
                        """
                    )
                )
            ).scalar_one()
            store_id = (
                await session.execute(
                    text(
                        """
                        INSERT INTO stores (org_id, slug, name, brand_name, platform)
                        VALUES (:org, 'lawn-bazaar', 'Lawn Bazaar', 'Lawn Bazaar', 'manual')
                        ON CONFLICT (org_id, slug) DO UPDATE SET name = EXCLUDED.name
                        RETURNING id
                        """
                    ),
                    {"org": org_id},
                )
            ).scalar_one()
            _log.info("seed.created", org_id=str(org_id), store_id=str(store_id))


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
