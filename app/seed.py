"""Generate deterministic synthetic accounts and transaction events."""

import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import create_schema, make_engine
from .models import Account, Transaction


@dataclass(frozen=True)
class SeedSummary:
    """Counts inserted by one successful seed operation."""

    accounts: int
    transactions: int


def seed_database(
    engine,
    *,
    account_count: int = 20,
    transaction_count: int = 100,
    seed: int = 2026,
) -> SeedSummary:
    """Insert repeatable synthetic records, refusing to mix them with existing rows."""
    if account_count < 2:
        raise ValueError("At least two accounts are required for transfer examples.")
    if transaction_count < 1:
        raise ValueError("transaction_count must be positive.")

    create_schema(engine)
    generator = random.Random(seed)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    transaction_types = ("deposit", "withdrawal", "transfer", "payment")
    type_weights = (20, 20, 35, 25)
    statuses = ("successful", "pending", "failed")
    status_weights = (88, 7, 5)

    with Session(engine) as session, session.begin():
        if session.scalar(select(Account.id).limit(1)) is not None or session.scalar(
            select(Transaction.id).limit(1)
        ) is not None:
            raise ValueError("Refusing to seed a database that already contains accounts or transactions.")

        accounts = [
            Account(synthetic_reference=f"SYN-ACCT-{number:04d}")
            for number in range(1, account_count + 1)
        ]
        session.add_all(accounts)
        session.flush()

        descriptions = {
            "deposit": "Synthetic cash deposit",
            "withdrawal": "Synthetic cash withdrawal",
            "transfer": "Synthetic account transfer",
            "payment": "Synthetic merchant payment",
        }
        records = []
        for number in range(1, transaction_count + 1):
            transaction_type = generator.choices(transaction_types, weights=type_weights, k=1)[0]
            status = generator.choices(statuses, weights=status_weights, k=1)[0]
            source = destination = None
            if transaction_type == "deposit":
                destination = generator.choice(accounts)
            elif transaction_type == "withdrawal":
                source = generator.choice(accounts)
            else:
                source, destination = generator.sample(accounts, 2)

            cents = generator.randint(250, 250_000)
            records.append(
                Transaction(
                    reference=f"SYN-TX-2025-{number:06d}",
                    source_account=source,
                    destination_account=destination,
                    transaction_type=transaction_type,
                    amount=Decimal(cents) / Decimal("100"),
                    currency="USD",
                    occurred_at=start + timedelta(
                        days=generator.randrange(31),
                        seconds=generator.randrange(86_400),
                    ),
                    status=status,
                    description=descriptions[transaction_type],
                )
            )
        session.add_all(records)

    return SeedSummary(accounts=account_count, transactions=transaction_count)


def main() -> None:
    """Create the configured schema and seed it once from the command line."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("Set DATABASE_URL to a MySQL connection URL before seeding.")

    engine = make_engine(database_url)
    summary = seed_database(engine)
    print(
        f"Inserted {summary.accounts} synthetic accounts and "
        f"{summary.transactions} synthetic transactions (USD, January 2025)."
    )


if __name__ == "__main__":
    main()
