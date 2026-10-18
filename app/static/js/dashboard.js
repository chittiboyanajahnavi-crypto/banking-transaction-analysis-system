(() => {
  "use strict";

  const STATUS_LABELS = { successful: "Successful", pending: "Pending", failed: "Failed" };
  const TYPE_LABELS = { deposit: "Deposit", withdrawal: "Withdrawal", transfer: "Transfer", payment: "Payment" };
  const STATUS_COLORS = { successful: "#347b74", pending: "#b28b4d", failed: "#a04b45" };
  const TYPE_COLORS = ["#244459", "#347b74", "#718b8c", "#a28b67"];
  const numberFormat = new Intl.NumberFormat(undefined);
  const integerFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });

  const $ = (id) => document.getElementById(id);
  const state = {
    summary: null,
    filters: { status: "", type: "", startDate: "2025-01-01", endDate: "2025-01-31", pageSize: 25 },
    page: 1,
    pagination: null,
    charts: { volume: null, status: null, type: null },
    requests: { volume: null, transactions: null },
    requestSequence: { volume: 0, transactions: 0 },
  };

  function setHidden(element, hidden) { element.hidden = hidden; }

  function formatMoney(decimalValue, currency) {
    if (decimalValue === null || decimalValue === undefined) return "—";
    const match = String(decimalValue).match(/^(-?)(\d+)(?:\.(\d{1,2}))?$/);
    if (!match) return `${currency} ${decimalValue}`;
    const [, sign, integerPart, fraction = ""] = match;
    const exactInteger = integerFormat.format(BigInt(integerPart));
    const cents = fraction.padEnd(2, "0");
    return `${sign}${currency} ${exactInteger}.${cents}`;
  }

  function displayDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", timeZone: "UTC", timeZoneName: "short",
    }).format(date);
  }

  function dateLabel(value) {
    const [year, month, day] = value.split("-").map(Number);
    return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", timeZone: "UTC" })
      .format(new Date(Date.UTC(year, month - 1, day)));
  }

  function friendlyError(error) {
    if (error instanceof window.TransactionApi.ApiRequestError) return error.message;
    return "Something went wrong while loading this section. Try again.";
  }

  function validateDateFilters(filters) {
    if (Boolean(filters.startDate) !== Boolean(filters.endDate)) {
      return "Choose both a start and end date, or clear both dates.";
    }
    if (filters.startDate && filters.endDate && filters.startDate > filters.endDate) {
      return "The start date must be on or before the end date.";
    }
    return "";
  }

  function updateActiveFilters() {
    const parts = [];
    if (state.filters.status) parts.push(`Status: ${STATUS_LABELS[state.filters.status] || state.filters.status}`);
    if (state.filters.type) parts.push(`Type: ${TYPE_LABELS[state.filters.type] || state.filters.type}`);
    if (state.filters.startDate && state.filters.endDate) {
      parts.push(`UTC dates: ${state.filters.startDate} through ${state.filters.endDate}`);
    }
    parts.push(`${state.filters.pageSize} rows per page`);
    $("active-filters").textContent = `Active filters · ${parts.join(" · ")}`;
  }

  function readFilters() {
    return {
      status: $("filter-status").value,
      type: $("filter-type").value,
      startDate: $("filter-start").value,
      endDate: $("filter-end").value,
      pageSize: Number($("filter-page-size").value),
    };
  }

  function renderSummary(summary) {
    state.summary = summary;
    $("metric-total").textContent = numberFormat.format(summary.total_transaction_count);
    $("metric-successful-count").textContent = numberFormat.format(summary.successful_transaction_count);
    $("metric-successful-value").textContent = formatMoney(summary.successful_transaction_value, summary.currency);
    $("metric-average").textContent = formatMoney(summary.average_successful_transaction_amount, summary.currency);
    $("metric-currency").textContent = `${summary.currency} · successful transactions only`;
    $("summary-status").textContent = "";
    $("summary-error").hidden = true;
    $("summary-metrics").hidden = false;
    $("summary-metrics").setAttribute("aria-busy", "false");
    renderCountChart("status", summary.counts_by_status, STATUS_LABELS, "Transaction count", Object.keys(summary.counts_by_status).map((key) => STATUS_COLORS[key] || "#718087"));
    renderCountChart("type", summary.counts_by_type, TYPE_LABELS, "Transaction count", TYPE_COLORS);
  }

  function renderCountChart(kind, values, labels, seriesLabel, colors) {
    const entries = Object.entries(values || {}).filter(([, count]) => Number.isFinite(count) && count > 0);
    const canvas = $(`${kind}-chart`);
    const empty = $(`${kind}-empty`);
    const error = $(`${kind}-error`);
    error.hidden = true;
    if (state.charts[kind]) {
      state.charts[kind].destroy();
      state.charts[kind] = null;
    }
    if (!entries.length) {
      canvas.parentElement.hidden = true;
      empty.textContent = "No transaction events are available for this chart.";
      empty.hidden = false;
      $(`${kind}-description`).textContent = empty.textContent;
      return;
    }
    empty.hidden = true;
    canvas.parentElement.hidden = false;
    if (!window.Chart) {
      canvas.parentElement.hidden = true;
      error.textContent = "The chart library could not be loaded. Summary values remain available.";
      error.hidden = false;
      return;
    }
    const chartLabels = entries.map(([key]) => labels[key] || key);
    const counts = entries.map(([, count]) => count);
    $(`${kind}-description`).textContent = `${chartLabels.map((label, index) => `${label}: ${numberFormat.format(counts[index])}`).join("; ")}.`;
    state.charts[kind] = new window.Chart(canvas, {
      type: kind === "status" ? "bar" : "bar",
      data: {
        labels: chartLabels,
        datasets: [{ label: seriesLabel, data: counts, backgroundColor: entries.map((_, index) => colors[index % colors.length]), borderRadius: 2, maxBarThickness: 34 }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (context) => `${seriesLabel}: ${numberFormat.format(context.parsed.x)}` } },
        },
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0, color: "#53616a" }, grid: { color: "#e5e8e3" }, title: { display: true, text: "Transaction count", color: "#53616a" } },
          y: { grid: { display: false }, ticks: { color: "#26343c" } },
        },
      },
    });
  }

  function renderVolume(volume) {
    const canvas = $("volume-chart");
    const empty = $("volume-empty");
    const error = $("volume-error");
    error.hidden = true;
    if (state.charts.volume) {
      state.charts.volume.destroy();
      state.charts.volume = null;
    }
    const days = volume.daily_volume || [];
    const totalEvents = days.reduce((total, day) => total + day.transaction_count, 0);
    if (!days.length || totalEvents === 0) {
      canvas.parentElement.hidden = true;
      empty.textContent = days.length ? "No transaction events occurred in this date range." : "Choose a start and end date to view daily volume.";
      empty.hidden = false;
      $("volume-description").textContent = empty.textContent;
      return;
    }
    empty.hidden = true;
    canvas.parentElement.hidden = false;
    if (!window.Chart) {
      canvas.parentElement.hidden = true;
      error.textContent = "The chart library could not be loaded. Try refreshing the page.";
      error.hidden = false;
      return;
    }
    const labels = days.map((day) => dateLabel(day.date));
    const counts = days.map((day) => day.transaction_count);
    $("volume-description").textContent = `Daily transaction counts: ${days.map((day) => `${day.date}: ${numberFormat.format(day.transaction_count)}`).join("; ")}.`;
    state.charts.volume = new window.Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [{ label: "Transactions", data: counts, borderColor: "#347b74", backgroundColor: "rgba(52, 123, 116, 0.10)", borderWidth: 2, fill: true, tension: 0.22, pointRadius: 3, pointHoverRadius: 5, pointBackgroundColor: "#347b74" }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { title: (items) => days[items[0].dataIndex]?.date || "", label: (context) => `Transactions: ${numberFormat.format(context.parsed.y)}` } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: "#53616a", maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }, title: { display: true, text: "Date (UTC)", color: "#53616a" } },
          y: { beginAtZero: true, ticks: { precision: 0, color: "#53616a" }, grid: { color: "#e5e8e3" }, title: { display: true, text: "Transaction count", color: "#53616a" } },
        },
      },
    });
  }

  function makeCell(text, className) {
    const cell = document.createElement("td");
    if (className) cell.className = className;
    cell.textContent = text;
    return cell;
  }

  function renderTransactions(body) {
    const tbody = $("transactions-body");
    tbody.replaceChildren();
    for (const row of body.data) {
      const tr = document.createElement("tr");
      tr.append(
        makeCell(row.reference),
        makeCell(displayDate(row.occurred_at)),
        makeCell(TYPE_LABELS[row.transaction_type] || row.transaction_type),
        makeCell(`From ${row.source_account_id ?? "—"} · To ${row.destination_account_id ?? "—"}`, "account-pair"),
      );
      const statusCell = document.createElement("td");
      const status = document.createElement("span");
      status.className = `status-label status-${row.status}`;
      status.textContent = STATUS_LABELS[row.status] || row.status;
      statusCell.append(status);
      tr.append(statusCell, makeCell(formatMoney(row.amount, row.currency), "amount-column"));
      tbody.append(tr);
    }
    const pagination = body.pagination;
    state.pagination = pagination;
    $("transactions-status").textContent = "";
    $("transactions-error").hidden = true;
    $("transactions-empty").hidden = body.data.length !== 0;
    $("transactions-empty").textContent = "No transactions match these filters.";
    $("pagination-summary").textContent = pagination.total_records === 0
      ? "0 transactions"
      : `${numberFormat.format(pagination.total_records)} transactions`;
    $("pagination-page").textContent = `Page ${pagination.page}${pagination.total_pages ? ` of ${pagination.total_pages}` : ""}`;
    $("previous-page").disabled = !pagination.has_previous;
    $("next-page").disabled = !pagination.has_next;
    document.querySelector(".table-scroll").setAttribute("aria-busy", "false");
  }

  async function loadVolume() {
    const sequence = ++state.requestSequence.volume;
    if (state.requests.volume) state.requests.volume.abort();
    if (state.charts.volume) {
      state.charts.volume.destroy();
      state.charts.volume = null;
    }
    const controller = new AbortController();
    state.requests.volume = controller;
    $("volume-error").hidden = true;
    $("volume-empty").hidden = true;
    $("volume-chart").parentElement.hidden = true;
    $("volume-empty").textContent = "Loading daily volume…";
    $("volume-empty").hidden = false;
    const invalid = validateDateFilters(state.filters);
    if (invalid) {
      controller.abort();
      $("volume-empty").hidden = true;
      $("volume-error").textContent = invalid;
      $("volume-error").hidden = false;
      return;
    }
    if (!state.filters.startDate) {
      $("volume-empty").textContent = "Choose a start and end date to view daily volume.";
      return;
    }
    try {
      const response = await window.TransactionApi.getVolume(state.filters.startDate, state.filters.endDate, { signal: controller.signal });
      if (sequence === state.requestSequence.volume) renderVolume(response.data);
    } catch (error) {
      if (error.name === "AbortError" || sequence !== state.requestSequence.volume) return;
      $("volume-empty").hidden = true;
      $("volume-error").textContent = friendlyError(error);
      $("volume-error").hidden = false;
    }
  }

  async function loadTransactions() {
    const sequence = ++state.requestSequence.transactions;
    if (state.requests.transactions) state.requests.transactions.abort();
    const controller = new AbortController();
    state.requests.transactions = controller;
    $("transactions-body").replaceChildren();
    $("transactions-error").hidden = true;
    $("transactions-empty").hidden = true;
    $("transactions-status").textContent = "Loading transactions…";
    $("pagination-summary").textContent = "Loading transactions…";
    $("pagination-page").textContent = `Page ${state.page}`;
    $("previous-page").disabled = true;
    $("next-page").disabled = true;
    document.querySelector(".table-scroll").setAttribute("aria-busy", "true");
    const invalid = validateDateFilters(state.filters);
    if (invalid) {
      controller.abort();
      $("transactions-status").textContent = "";
      $("transactions-error").textContent = invalid;
      $("transactions-error").hidden = false;
      document.querySelector(".table-scroll").setAttribute("aria-busy", "false");
      return;
    }
    try {
      const response = await window.TransactionApi.getTransactions(state.filters, state.page, { signal: controller.signal });
      if (sequence === state.requestSequence.transactions) renderTransactions(response);
    } catch (error) {
      if (error.name === "AbortError" || sequence !== state.requestSequence.transactions) return;
      $("transactions-status").textContent = "";
      $("transactions-error").textContent = friendlyError(error);
      $("transactions-error").hidden = false;
      $("pagination-summary").textContent = "Transaction count unavailable";
      $("pagination-page").textContent = `Page ${state.page}`;
      $("previous-page").disabled = true;
      $("next-page").disabled = true;
      document.querySelector(".table-scroll").setAttribute("aria-busy", "false");
    }
  }

  async function loadSummary() {
    $("summary-status").textContent = "Loading summary…";
    $("summary-error").hidden = true;
    $("summary-metrics").hidden = true;
    try {
      const response = await window.TransactionApi.getSummary();
      renderSummary(response.data);
    } catch (error) {
      $("summary-status").textContent = "";
      $("summary-error").textContent = friendlyError(error);
      $("summary-error").hidden = false;
      $("summary-metrics").setAttribute("aria-busy", "false");
      for (const kind of ["status", "type"]) {
        $(`${kind}-chart`).parentElement.hidden = true;
        $(`${kind}-empty`).hidden = true;
        $(`${kind}-error`).textContent = friendlyError(error);
        $(`${kind}-error`).hidden = false;
      }
    }
  }

  function reloadFilteredData() {
    updateActiveFilters();
    loadVolume();
    loadTransactions();
  }

  function resetFilters() {
    $("filters-form").reset();
    $("filter-start").value = "2025-01-01";
    $("filter-end").value = "2025-01-31";
    $("filter-page-size").value = "25";
    state.filters = { status: "", type: "", startDate: "2025-01-01", endDate: "2025-01-31", pageSize: 25 };
    state.page = 1;
    reloadFilteredData();
  }

  function initialize() {
    $("filters-form").addEventListener("submit", (event) => {
      event.preventDefault();
      state.filters = readFilters();
      state.page = 1;
      reloadFilteredData();
    });
    $("reset-filters").addEventListener("click", resetFilters);
    $("previous-page").addEventListener("click", () => {
      if (state.pagination?.has_previous) {
        state.page -= 1;
        loadTransactions();
      }
    });
    $("next-page").addEventListener("click", () => {
      if (state.pagination?.has_next) {
        state.page += 1;
        loadTransactions();
      }
    });
    updateActiveFilters();
    loadSummary();
    loadVolume();
    loadTransactions();
  }

  document.addEventListener("DOMContentLoaded", initialize);
})();
