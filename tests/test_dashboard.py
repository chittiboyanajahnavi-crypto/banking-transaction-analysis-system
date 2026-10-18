from app import create_app


def test_dashboard_route_serves_accessible_frontend_shell_without_database():
    app = create_app({"TESTING": True, "DATABASE_URL": None})
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    html = response.get_data(as_text=True)
    assert "Banking Transaction Analysis System" in html
    assert 'id="summary-metrics"' in html
    assert 'id="volume-chart"' in html
    assert 'id="transactions-body"' in html
    assert 'id="filter-status"' in html
    assert 'id="filter-type"' in html
    assert 'id="previous-page"' in html
    assert 'href="/static/css/dashboard.css"' in html
    assert 'src="/static/js/api.js"' in html
    assert 'src="/static/js/dashboard.js"' in html
    assert 'src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js"' in html


def test_dashboard_assets_are_served_by_flask():
    app = create_app({"TESTING": True, "DATABASE_URL": None})
    client = app.test_client()

    css = client.get("/static/css/dashboard.css")
    api_js = client.get("/static/js/api.js")
    dashboard_js = client.get("/static/js/dashboard.js")

    assert css.status_code == 200
    assert "text/css" in css.mimetype
    assert "prefers-reduced-motion" in css.get_data(as_text=True)
    assert api_js.status_code == 200
    assert api_js.mimetype in {"application/javascript", "text/javascript"}
    assert "getTransactions" in api_js.get_data(as_text=True)
    assert dashboard_js.status_code == 200
    assert dashboard_js.mimetype in {"application/javascript", "text/javascript"}
    assert "destroy()" in dashboard_js.get_data(as_text=True)
    assert "No transactions match these filters." in dashboard_js.get_data(as_text=True)
