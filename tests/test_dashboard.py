import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "DATABASE_URL": None})
    return app.test_client()


@pytest.mark.parametrize(
    ("path", "page"),
    [("/", "overview"), ("/transactions", "transactions"), ("/analysis", "analysis")],
)
def test_three_pages_serve_shared_navigation_with_correct_active_page(client, path, page):
    response = client.get(path)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    html = response.get_data(as_text=True)
    assert f'<body data-page="{page}">' in html
    assert 'href="/"' in html
    assert 'href="/transactions"' in html
    assert 'href="/analysis"' in html
    assert f'href="{path}" aria-current="page"' in html
    assert "Synthetic demonstration data" in html
    assert 'href="/static/css/dashboard.css"' in html
    assert 'src="/static/js/api.js"' in html
    assert 'src="/static/js/dashboard.js"' in html
    chart_script = 'src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js"'
    assert (chart_script in html) is (page != "transactions")


def test_pages_keep_distinct_purposes(client):
    overview = client.get("/").get_data(as_text=True)
    transactions = client.get("/transactions").get_data(as_text=True)
    analysis = client.get("/analysis").get_data(as_text=True)

    assert 'id="metric-total"' in overview
    assert 'id="overview-volume-chart"' in overview
    assert 'id="transactions-body"' not in overview
    assert 'id="transactions-body"' in transactions
    assert 'id="filter-status"' in transactions
    assert 'id="analysis-start"' not in transactions
    assert 'id="analysis-start"' in analysis
    assert 'id="analysis-deposits"' in analysis
    assert 'id="analysis-withdrawals"' in analysis
    assert "Through date (UTC, inclusive)" in analysis


def test_dashboard_date_controls_and_overview_describe_cutoff(client):
    overview = client.get("/").get_data(as_text=True)
    transactions = client.get("/transactions").get_data(as_text=True)
    analysis = client.get("/analysis").get_data(as_text=True)

    assert "THROUGH OCTOBER 18, 2026 · UTC" in overview
    assert "ALL-TIME" not in overview
    assert transactions.count('max="2026-10-18"') == 2
    assert analysis.count('max="2026-10-18"') == 2


def test_frontend_assets_are_served_by_flask(client):
    css = client.get("/static/css/dashboard.css")
    api_js = client.get("/static/js/api.js")
    dashboard_js = client.get("/static/js/dashboard.js")

    assert css.status_code == 200
    assert "text/css" in css.mimetype
    assert "prefers-reduced-motion" in css.get_data(as_text=True)
    assert api_js.status_code == 200
    assert api_js.mimetype in {"application/javascript", "text/javascript"}
    assert "getAnalysis" in api_js.get_data(as_text=True)
    assert dashboard_js.status_code == 200
    assert dashboard_js.mimetype in {"application/javascript", "text/javascript"}
    assert "aria-busy" in dashboard_js.get_data(as_text=True)
    assert "No transaction events are available for this chart." in dashboard_js.get_data(as_text=True)
