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


DEFAULT_TRANSACTION_COUNT = 1_200
LEGACY_JANUARY_COUNT = 100
DAILY_EXTENSION_COUNT = 700
EXTENSION_START_OFFSET = 31
DATASET_START = datetime(2025, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class SeedSummary:
    """Counts inserted by one successful seed operation."""

    accounts: int
    transactions: int


def seed_database(
    engine,
    *,
    account_count: int = 20,
    transaction_count: int = DEFAULT_TRANSACTION_COUNT,
    seed: int = 2026,
) -> SeedSummary:
    """Add deterministic synthetic rows without changing existing database records.

    The first 100 events retain their original January 2025 generation so existing
    development databases can be extended without rewriting their seed records.
    Later events add one synthetic event per day through January 1, 2027. Existing
    account and transaction references are left untouched and skipped on reruns.
    """
    if account_count < 2:
        raise ValueError("At least two accounts are required for transfer examples.")
    if transaction_count < 1:
        raise ValueError("transaction_count must be positive.")

    create_schema(engine)
    generator = random.Random(seed)
    transaction_types = ("deposit", "withdrawal", "transfer", "payment")
    type_weights = (20, 20, 35, 25)
    statuses = ("successful", "pending", "failed")
    status_weights = (88, 7, 5)

    with Session(engine) as session, session.begin():
        account_references = [f"SYN-ACCT-{number:04d}" for number in range(1, account_count + 1)]
        existing_accounts = {
            account.synthetic_reference: account
            for account in session.scalars(
                select(Account).where(Account.synthetic_reference.in_(account_references))
            )
        }
        accounts_added = 0
        for reference in account_references:
            if reference not in existing_accounts:
                account = Account(synthetic_reference=reference)
                session.add(account)
                existing_accounts[reference] = account
                accounts_added += 1
        session.flush()
        accounts = [existing_accounts[reference] for reference in account_references]

        descriptions = {
            "deposit": "Synthetic cash deposit",
            "withdrawal": "Synthetic cash withdrawal",
            "transfer": "Synthetic account transfer",
            "payment": "Synthetic merchant payment",
        }
        record_specs = []
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
            if number <= LEGACY_JANUARY_COUNT:
                occurred_at = DATASET_START + timedelta(
                    days=generator.randrange(31),
                    seconds=generator.randrange(86_400),
                )
            elif number <= LEGACY_JANUARY_COUNT + DAILY_EXTENSION_COUNT:
                # Preserve the continuous one-event-per-day backbone.
                occurred_at = DATASET_START + timedelta(
                    days=EXTENSION_START_OFFSET + number - LEGACY_JANUARY_COUNT - 1,
                    seconds=generator.randrange(86_400),
                )
            else:
                # Add irregular daily volume while keeping every day in the range populated.
                occurred_at = DATASET_START + timedelta(
                    days=EXTENSION_START_OFFSET + generator.randrange(DAILY_EXTENSION_COUNT),
                    seconds=generator.randrange(86_400),
                )
            record_specs.append(
                {
                    "reference": f"SYN-TX-{occurred_at.year}-{number:06d}",
                    "source_account": source,
                    "destination_account": destination,
                    "transaction_type": transaction_type,
                    "amount": Decimal(cents) / Decimal("100"),
                    "occurred_at": occurred_at,
                    "status": status,
                    "description": descriptions[transaction_type],
                }
            )
        with session.no_autoflush:
            existing_references = set(
                session.scalars(
                    select(Transaction.reference).where(
                        Transaction.reference.in_([spec["reference"] for spec in record_specs])
                    )
                )
            )
        records_to_add = [
            Transaction(**spec)
            for spec in record_specs
            if spec["reference"] not in existing_references
        ]
        session.add_all(records_to_add)

    return SeedSummary(accounts=accounts_added, transactions=len(records_to_add))


def main() -> None:
    """Create the configured schema and seed it once from the command line."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("Set DATABASE_URL to a MySQL connection URL before seeding.")

    engine = make_engine(database_url)
    summary = seed_database(engine)
    print(
        f"Inserted {summary.accounts} synthetic accounts and "
        f"{summary.transactions} synthetic transactions (USD, January 1, 2025 "
        f"through January 1, 2027; default total {DEFAULT_TRANSACTION_COUNT})."
    )


if __name__ == "__main__":
    main()
