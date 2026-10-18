from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import create_schema, make_engine
from app.models import Account, Transaction
from app.seed import seed_database


def make_test_engine():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    return engine


def test_seed_is_deterministic_and_refuses_existing_data():
    engine = make_test_engine()

    result = seed_database(engine, account_count=6, transaction_count=40, seed=123)

    assert result.accounts == 6
    assert result.transactions == 40
    with Session(engine) as session:
        rows = session.scalars(select(Transaction).order_by(Transaction.reference)).all()
        assert len(rows) == 40
        assert {row.currency for row in rows} == {"USD"}
        assert {row.status for row in rows} == {"successful", "pending", "failed"}
        assert {row.transaction_type for row in rows} == {
            "deposit", "withdrawal", "transfer", "payment"
        }
        assert all(row.amount > Decimal("0") for row in rows)
        first_run = [
            (row.reference, row.transaction_type, row.amount, row.occurred_at, row.status)
            for row in rows
        ]

    second_engine = make_test_engine()
    seed_database(second_engine, account_count=6, transaction_count=40, seed=123)
    with Session(second_engine) as session:
        second_run = [
            (row.reference, row.transaction_type, row.amount, row.occurred_at, row.status)
            for row in session.scalars(select(Transaction).order_by(Transaction.reference)).all()
        ]
    assert first_run == second_run

    with pytest.raises(ValueError, match="already contains"):
        seed_database(engine, account_count=6, transaction_count=40, seed=123)


def test_schema_rejects_invalid_amount_and_missing_account_reference():
    engine = make_test_engine()
    with Session(engine) as session, session.begin():
        session.add(Account(synthetic_reference="SYN-ACCT-0001"))

    invalid_rows = (
        Transaction(
            reference="SYN-TX-INVALID-AMOUNT",
            source_account_id=1,
            transaction_type="withdrawal",
            amount=Decimal("0.00"),
            currency="USD",
            occurred_at=datetime(2025, 1, 1),
            status="successful",
        ),
        Transaction(
            reference="SYN-TX-MISSING-ACCOUNT",
            source_account_id=999,
            transaction_type="withdrawal",
            amount=Decimal("1.00"),
            currency="USD",
            occurred_at=datetime(2025, 1, 1),
            status="successful",
        ),
    )
    for transaction in invalid_rows:
        with pytest.raises(IntegrityError):
            with Session(engine) as session:
                session.add(transaction)
                session.commit()
