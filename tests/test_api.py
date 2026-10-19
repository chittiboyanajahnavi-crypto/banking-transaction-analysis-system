from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app import create_app
from app.database import create_schema
from app.models import Account, Transaction
from app.seed import seed_database


@pytest.fixture
def app():
    application = create_app(
        {"TESTING": True, "DATABASE_URL": "sqlite+pysqlite:///:memory:"}
    )
    create_schema(application.extensions["database_engine"])
    yield application
    application.extensions["database_engine"].dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def utc(day, hour=0):
    return datetime(2025, 1, day, hour, tzinfo=timezone.utc)


def insert_transactions(app, entries):
    engine = app.extensions["database_engine"]
    with Session(engine) as session, session.begin():
        source = Account(synthetic_reference="SYN-API-ACCOUNT-0001")
        destination = Account(synthetic_reference="SYN-API-ACCOUNT-0002")
        session.add_all([source, destination])
        session.flush()

        for index, entry in enumerate(entries, start=1):
            transaction_type, status, amount, occurred_at = entry[:4]
            source_account = None if transaction_type == "deposit" else source
            destination_account = None if transaction_type == "withdrawal" else destination
            session.add(
                Transaction(
                    reference=f"SYN-API-TX-{index:04d}",
                    source_account=source_account,
                    destination_account=destination_account,
                    transaction_type=transaction_type,
                    amount=Decimal(str(amount)),
                    currency="USD",
                    occurred_at=occurred_at,
                    status=status,
                    description=f"Synthetic test event {index}",
                )
            )


def populated_entries():
    return [
        ("deposit", "successful", "10.10", utc(1)),
        ("withdrawal", "successful", "2.25", utc(1, 12)),
        ("transfer", "successful", "3.33", utc(2)),
        ("payment", "successful", "4.00", utc(2, 12)),
        ("deposit", "pending", "100.00", utc(1, 23)),
        ("withdrawal", "failed", "50.00", utc(2, 23)),
    ]


def assert_error(response, status, code):
    assert response.status_code == status
    assert response.is_json
    body = response.get_json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert isinstance(body["error"]["message"], str)


def test_health_remains_available_without_database_configuration():
    app_without_database = create_app({"TESTING": True, "DATABASE_URL": None})

    response = app_without_database.test_client().get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_summary_returns_real_metrics_and_decimal_strings(client, app):
    insert_transactions(app, populated_entries())

    response = client.get("/api/analytics/summary")

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data == {
        "currency": "USD",
        "total_transaction_count": 6,
        "successful_transaction_count": 4,
        "successful_transaction_value": "19.68",
        "average_successful_transaction_amount": "4.92",
        "counts_by_status": {"failed": 1, "pending": 1, "successful": 4},
        "counts_by_type": {"deposit": 2, "payment": 1, "transfer": 1, "withdrawal": 2},
        "successful_deposit_total": "10.10",
        "successful_withdrawal_total": "2.25",
        "daily_volume": [
            {"date": "2025-01-01", "transaction_count": 3},
            {"date": "2025-01-02", "transaction_count": 3},
        ],
    }
    assert isinstance(data["successful_transaction_value"], str)
    assert not isinstance(data["successful_transaction_value"], float)


def test_cutoff_applies_to_summary_volume_listing_and_pagination(client, app):
    cutoff = datetime(2026, 10, 19, tzinfo=timezone.utc)
    insert_transactions(
        app,
        [
            ("deposit", "successful", "1.25", cutoff - timedelta(seconds=1)),
            ("withdrawal", "successful", "2.75", datetime(2026, 10, 18, 23, 59, 59, 999999, tzinfo=timezone.utc)),
            ("transfer", "successful", "100.00", cutoff),
            ("payment", "successful", "200.00", cutoff + timedelta(days=1)),
        ],
    )

    summary = client.get("/api/analytics/summary").get_json()["data"]
    volume = client.get(
        "/api/analytics/volume?start_date=2026-10-18&end_date=2026-10-20"
    ).get_json()["data"]
    first_page = client.get("/api/transactions?page_size=1").get_json()
    second_page = client.get("/api/transactions?page=2&page_size=1").get_json()
    bounded_listing = client.get(
        "/api/transactions?start_date=2026-10-18&end_date=2026-10-20&page_size=1"
    ).get_json()

    assert summary["total_transaction_count"] == 2
    assert summary["successful_transaction_value"] == "4.00"
    assert summary["average_successful_transaction_amount"] == "2.00"
    assert volume["total_transaction_count"] == 2
    assert volume["successful_transaction_value"] == "4.00"
    assert volume["daily_volume"][0] == {"date": "2026-10-18", "transaction_count": 2}
    assert first_page["pagination"]["total_records"] == 2
    assert first_page["pagination"]["total_pages"] == 2
    assert second_page["pagination"]["total_records"] == 2
    assert [first_page["data"][0]["reference"], second_page["data"][0]["reference"]] == [
        "SYN-API-TX-0002",
        "SYN-API-TX-0001",
    ]
    assert first_page["data"][0]["occurred_at"] == "2026-10-18T23:59:59.999999Z"
    assert second_page["data"][0]["occurred_at"] == "2026-10-18T23:59:59.000000Z"
    assert bounded_listing["pagination"]["total_records"] == 2
    assert bounded_listing["pagination"]["total_pages"] == 2


def test_future_only_date_filters_return_zero_without_exposing_records(client, app):
    cutoff = datetime(2026, 10, 19, tzinfo=timezone.utc)
    insert_transactions(
        app,
        [("deposit", "successful", "50.00", cutoff + datetime.resolution)],
    )

    volume = client.get(
        "/api/analytics/volume?start_date=2026-10-19&end_date=2026-10-21"
    ).get_json()["data"]
    listing = client.get(
        "/api/transactions?start_date=2026-10-19&end_date=2026-10-21"
    ).get_json()

    assert volume["total_transaction_count"] == 0
    assert volume["successful_transaction_value"] == "0.00"
    assert volume["daily_volume"] == [
        {"date": "2026-10-19", "transaction_count": 0},
        {"date": "2026-10-20", "transaction_count": 0},
    ]
    assert listing["data"] == []
    assert listing["pagination"]["total_records"] == 0
    assert listing["pagination"]["total_pages"] == 0


def test_empty_summary_has_zero_values_and_null_average(client):
    response = client.get("/api/analytics/summary")

    assert response.status_code == 200
    assert response.get_json()["data"] == {
        "currency": "USD",
        "total_transaction_count": 0,
        "successful_transaction_count": 0,
        "successful_transaction_value": "0.00",
        "average_successful_transaction_amount": None,
        "counts_by_status": {},
        "counts_by_type": {},
        "successful_deposit_total": "0.00",
        "successful_withdrawal_total": "0.00",
        "daily_volume": [],
    }


def test_summary_fills_zero_count_days_between_all_time_events(client, app):
    insert_transactions(
        app,
        [
            ("deposit", "successful", "1.00", utc(1)),
            ("payment", "pending", "2.00", utc(3)),
        ],
    )

    response = client.get("/api/analytics/summary")

    assert response.status_code == 200
    assert response.get_json()["data"]["daily_volume"] == [
        {"date": "2025-01-01", "transaction_count": 1},
        {"date": "2025-01-02", "transaction_count": 0},
        {"date": "2025-01-03", "transaction_count": 1},
    ]


def test_volume_uses_utc_inclusive_start_and_exclusive_end(client, app):
    insert_transactions(
        app,
        [
            ("deposit", "successful", "1.00", utc(1)),
            ("withdrawal", "pending", "2.00", utc(2, 12)),
            ("transfer", "successful", "3.00", utc(3)),
        ],
    )

    response = client.get(
        "/api/analytics/volume?start_date=2025-01-01&end_date=2025-01-03"
    )

    assert response.status_code == 200
    assert response.get_json()["data"] == {
        "start_date_inclusive": "2025-01-01",
        "end_date_exclusive": "2025-01-03",
        "timezone": "UTC",
        "currency": "USD",
        "total_transaction_count": 2,
        "successful_transaction_count": 1,
        "successful_transaction_value": "1.00",
        "average_successful_transaction_amount": "1.00",
        "counts_by_status": {"pending": 1, "successful": 1},
        "counts_by_type": {"deposit": 1, "withdrawal": 1},
        "successful_deposit_total": "1.00",
        "successful_withdrawal_total": "0.00",
        "daily_volume": [
            {"date": "2025-01-01", "transaction_count": 1},
            {"date": "2025-01-02", "transaction_count": 1},
        ],
    }


def test_seeded_data_appears_across_years_and_empty_ranges_stay_empty(client, app):
    seed_database(app.extensions["database_engine"])

    january_2023 = client.get(
        "/api/analytics/volume?start_date=2023-01-01&end_date=2023-02-01"
    ).get_json()["data"]
    january_2025 = client.get(
        "/api/analytics/volume?start_date=2025-01-01&end_date=2025-02-01"
    ).get_json()["data"]
    january_2026 = client.get(
        "/api/analytics/volume?start_date=2026-01-01&end_date=2026-02-01"
    ).get_json()["data"]
    january_2026_transactions = client.get(
        "/api/transactions?start_date=2026-01-01&end_date=2026-02-01"
    ).get_json()
    october_2026 = client.get(
        "/api/analytics/volume?start_date=2026-10-01&end_date=2026-10-19"
    ).get_json()["data"]

    assert january_2023["total_transaction_count"] >= 31
    assert len(january_2023["daily_volume"]) == 31
    assert all(day["transaction_count"] >= 1 for day in january_2023["daily_volume"])
    assert january_2025["total_transaction_count"] == 100
    assert january_2026["total_transaction_count"] >= 31
    assert len(january_2026["daily_volume"]) == 31
    assert all(day["transaction_count"] >= 1 for day in january_2026["daily_volume"])
    assert sum(day["transaction_count"] for day in january_2026["daily_volume"]) == january_2026[
        "total_transaction_count"
    ]
    assert january_2026_transactions["pagination"]["total_records"] == january_2026[
        "total_transaction_count"
    ]
    assert october_2026["total_transaction_count"] >= 18
    assert len(october_2026["daily_volume"]) == 18
    assert all(day["transaction_count"] >= 1 for day in october_2026["daily_volume"])

    empty_analysis = client.get(
        "/api/analytics/volume?start_date=2027-02-01&end_date=2027-03-01"
    ).get_json()["data"]
    empty_transactions = client.get(
        "/api/transactions?start_date=2027-02-01&end_date=2027-03-01"
    ).get_json()

    assert empty_analysis["total_transaction_count"] == 0
    assert empty_analysis["successful_transaction_count"] == 0
    assert empty_analysis["successful_transaction_value"] == "0.00"
    assert empty_analysis["counts_by_status"] == {}
    assert empty_analysis["counts_by_type"] == {}
    assert len(empty_analysis["daily_volume"]) == 28
    assert all(day["transaction_count"] == 0 for day in empty_analysis["daily_volume"])
    assert empty_transactions["data"] == []
    assert empty_transactions["pagination"]["total_records"] == 0


@pytest.mark.parametrize(
    "query",
    [
        "",
        "?start_date=2025-01-01",
        "?end_date=2025-01-02",
        "?start_date=01-01-2025&end_date=2025-01-02",
        "?start_date=2025-02-30&end_date=2025-03-01",
        "?start_date=2025-01-03&end_date=2025-01-02",
        "?start_date=2025-01-02&end_date=2025-01-02",
    ],
)
def test_volume_rejects_missing_malformed_or_reversed_dates(client, query):
    assert_error(client.get(f"/api/analytics/volume{query}"), 400, "invalid_query_parameter")


def test_empty_volume_range_returns_zero_days(client):
    response = client.get(
        "/api/analytics/volume?start_date=2025-01-01&end_date=2025-01-04"
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["daily_volume"] == [
        {"date": "2025-01-01", "transaction_count": 0},
        {"date": "2025-01-02", "transaction_count": 0},
        {"date": "2025-01-03", "transaction_count": 0},
    ]


def test_transaction_listing_uses_default_pagination_and_stable_tie_breaker(client, app):
    same_time = utc(1)
    insert_transactions(
        app,
        [("deposit", "successful", "2.50", same_time) for _ in range(30)],
    )

    first_page = client.get("/api/transactions")
    second_page = client.get("/api/transactions?page=2")

    assert first_page.status_code == 200
    first = first_page.get_json()
    second = second_page.get_json()
    assert first["pagination"] == {
        "page": 1,
        "page_size": 25,
        "total_records": 30,
        "total_pages": 2,
        "has_previous": False,
        "has_next": True,
    }
    assert len(first["data"]) == 25
    assert len(second["data"]) == 5
    assert first["data"][0]["reference"] == "SYN-API-TX-0030"
    assert first["data"][-1]["reference"] == "SYN-API-TX-0006"
    assert second["data"][0]["reference"] == "SYN-API-TX-0005"
    assert first["data"][0]["amount"] == "2.50"
    assert first["data"][0]["occurred_at"] == "2025-01-01T00:00:00.000000Z"
    assert set(first["data"][0]) == {
        "id", "reference", "source_account_id", "destination_account_id",
        "transaction_type", "amount", "currency", "occurred_at", "status", "description",
    }


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("page=0", "page"),
        ("page=-1", "page"),
        ("page=abc", "page"),
        ("page_size=0", "page_size"),
        ("page_size=101", "not exceed 100"),
        ("status=complete", "status"),
        ("transaction_type=refund", "transaction_type"),
        ("start_date=bad&end_date=2025-01-02", "YYYY-MM-DD"),
        ("start_date=2025-02-30&end_date=2025-03-01", "calendar date"),
        ("start_date=2025-01-03&end_date=2025-01-02", "earlier"),
        ("start_date=2025-01-01", "supplied together"),
    ],
)
def test_transaction_listing_validates_pagination_filters_and_dates(client, query, message):
    response = client.get(f"/api/transactions?{query}")
    assert_error(response, 400, "invalid_query_parameter")
    assert message in response.get_json()["error"]["message"]


def test_transaction_listing_applies_supported_status_type_and_date_filters(client, app):
    insert_transactions(app, populated_entries())

    response = client.get(
        "/api/transactions?status=successful&transaction_type=deposit"
        "&start_date=2025-01-01&end_date=2025-01-02"
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["pagination"]["total_records"] == 1
    assert body["data"][0]["reference"] == "SYN-API-TX-0001"


def test_errors_are_json_and_database_unavailability_does_not_expose_configuration():
    app_without_database = create_app({"TESTING": True, "DATABASE_URL": None})
    client = app_without_database.test_client()

    assert_error(client.get("/api/analytics/summary"), 503, "database_unavailable")
    assert_error(client.get("/api/not-a-route"), 404, "not_found")
    assert_error(client.get("/api/analytics/summary?unexpected=value"), 400, "invalid_query_parameter")
