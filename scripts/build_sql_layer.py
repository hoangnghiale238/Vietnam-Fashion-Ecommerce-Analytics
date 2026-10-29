from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path(os.environ.get("VN_FASHION_SOURCE_DIR", PROJECT_DIR / "data" / "cleaned"))
DATA_DIR = PROJECT_DIR / "data"
EXPORT_DIR = DATA_DIR / "outputs"
SITE_DATA_DIR = PROJECT_DIR / "website" / "data"
DATABASE_PATH = DATA_DIR / "vn_fashion_analytics.sqlite"
TEMP_DATABASE_PATH = DATA_DIR / "vn_fashion_analytics.sqlite.tmp"

SOURCE_FILES = {
    "customers": "customers_clean.csv",
    "orders": "orders_clean.csv",
    "order_items": "order_items_clean.csv",
    "products": "products_clean.csv",
    "returns": "returns_clean.csv",
}

INDEXES = [
    "CREATE UNIQUE INDEX idx_customers_id ON customers(customer_id)",
    "CREATE UNIQUE INDEX idx_orders_id ON orders(order_id)",
    "CREATE INDEX idx_orders_date ON orders(order_date)",
    "CREATE INDEX idx_orders_customer ON orders(customer_id)",
    "CREATE INDEX idx_orders_status ON orders(order_status)",
    "CREATE INDEX idx_order_items_order ON order_items(order_id)",
    "CREATE INDEX idx_order_items_product ON order_items(product_id)",
    "CREATE UNIQUE INDEX idx_products_id ON products(product_id)",
    "CREATE UNIQUE INDEX idx_returns_id ON returns(return_id)",
    "CREATE INDEX idx_returns_order_product ON returns(order_id, product_id)",
]

VIEW_SQL = """
DROP VIEW IF EXISTS vw_return_by_order_product;
DROP VIEW IF EXISTS vw_order_product_financials;
DROP VIEW IF EXISTS vw_order_financials;
DROP VIEW IF EXISTS vw_order_analytics;
DROP VIEW IF EXISTS vw_sales_detail;

CREATE VIEW vw_return_by_order_product AS
SELECT
    order_id,
    product_id,
    COUNT(DISTINCT return_id) AS return_records,
    SUM(return_quantity) AS returned_units,
    SUM(refund_amount) AS refund_amount
FROM returns
GROUP BY order_id, product_id;

CREATE VIEW vw_order_product_financials AS
SELECT
    oi.order_id,
    oi.product_id,
    SUM(oi.quantity) AS units,
    SUM(oi.line_value) AS gross_value,
    SUM(oi.discount_amount) AS discount_amount,
    SUM(oi.net_value) AS net_value,
    SUM(oi.quantity * p.cogs) AS cogs,
    SUM(oi.net_value - oi.quantity * p.cogs) AS gross_profit
FROM order_items AS oi
JOIN products AS p
  ON p.product_id = oi.product_id
GROUP BY oi.order_id, oi.product_id;

CREATE VIEW vw_order_financials AS
SELECT
    order_id,
    SUM(units) AS units,
    SUM(gross_value) AS gross_value,
    SUM(discount_amount) AS discount_amount,
    SUM(net_value) AS net_value,
    SUM(cogs) AS cogs,
    SUM(gross_profit) AS gross_profit
FROM vw_order_product_financials
GROUP BY order_id;

CREATE VIEW vw_order_analytics AS
SELECT
    o.order_id,
    o.order_date,
    CAST(strftime('%Y', o.order_date) AS INTEGER) AS order_year,
    strftime('%Y-%m', o.order_date) AS order_month,
    o.customer_id,
    o.zip,
    o.order_status,
    o.payment_method,
    o.device_type,
    o.order_source,
    c.city,
    c.gender,
    c.age_group,
    c.acquisition_channel,
    f.units,
    f.gross_value,
    f.discount_amount,
    f.net_value,
    f.cogs,
    f.gross_profit
FROM orders AS o
JOIN vw_order_financials AS f
  ON f.order_id = o.order_id
LEFT JOIN customers AS c
  ON c.customer_id = o.customer_id;

CREATE VIEW vw_sales_detail AS
SELECT
    o.order_id,
    o.order_date,
    CAST(strftime('%Y', o.order_date) AS INTEGER) AS order_year,
    strftime('%Y-%m', o.order_date) AS order_month,
    o.customer_id,
    o.order_status,
    o.payment_method,
    o.device_type,
    o.order_source,
    c.city,
    c.gender,
    c.age_group,
    c.acquisition_channel,
    p.product_id,
    p.product_name,
    p.category,
    p.segment,
    p.size,
    p.color,
    op.units,
    op.gross_value,
    op.discount_amount,
    op.net_value,
    op.cogs,
    op.gross_profit,
    COALESCE(r.return_records, 0) AS return_records,
    COALESCE(r.returned_units, 0) AS returned_units,
    COALESCE(r.refund_amount, 0) AS refund_amount
FROM vw_order_product_financials AS op
JOIN orders AS o
  ON o.order_id = op.order_id
JOIN products AS p
  ON p.product_id = op.product_id
LEFT JOIN customers AS c
  ON c.customer_id = o.customer_id
LEFT JOIN vw_return_by_order_product AS r
  ON r.order_id = op.order_id
 AND r.product_id = op.product_id;
"""

QUERIES = {
    "status_summary": """
        SELECT order_status,
               COUNT(*) AS orders,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS order_share_pct
        FROM orders
        GROUP BY order_status
        ORDER BY orders DESC
    """,
    "monthly_performance": """
        SELECT order_month AS month,
               COUNT(*) AS total_orders,
               SUM(order_status = 'delivered') AS delivered_orders,
               SUM(order_status = 'cancelled') AS cancelled_orders,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 2) AS delivered_net_sales,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN gross_profit ELSE 0 END), 2) AS delivered_gross_profit,
               ROUND(100.0 * SUM(CASE WHEN order_status = 'delivered' THEN gross_profit ELSE 0 END)
                   / NULLIF(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 0), 2) AS gross_margin_pct,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END)
                   / NULLIF(SUM(order_status = 'delivered'), 0), 2) AS average_order_value,
               ROUND(100.0 * SUM(order_status = 'delivered') / COUNT(*), 2) AS delivered_share_pct,
               ROUND(100.0 * SUM(order_status = 'cancelled') / COUNT(*), 2) AS cancellation_rate_pct
        FROM vw_order_analytics
        GROUP BY order_month
        ORDER BY order_month
    """,
    "annual_performance": """
        SELECT order_year AS year,
               COUNT(*) AS total_orders,
               SUM(order_status = 'delivered') AS delivered_orders,
               SUM(order_status = 'cancelled') AS cancelled_orders,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 2) AS delivered_net_sales,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN gross_profit ELSE 0 END), 2) AS delivered_gross_profit,
               ROUND(100.0 * SUM(CASE WHEN order_status = 'delivered' THEN gross_profit ELSE 0 END)
                   / NULLIF(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 0), 2) AS gross_margin_pct,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END)
                   / NULLIF(SUM(order_status = 'delivered'), 0), 2) AS average_order_value
        FROM vw_order_analytics
        GROUP BY order_year
        ORDER BY order_year
    """,
    "category_performance": """
        SELECT category,
               COUNT(DISTINCT CASE WHEN order_status = 'delivered' THEN order_id END) AS delivered_orders,
               SUM(CASE WHEN order_status = 'delivered' THEN units ELSE 0 END) AS delivered_units,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 2) AS delivered_net_sales,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN gross_profit ELSE 0 END), 2) AS delivered_gross_profit,
               ROUND(100.0 * SUM(CASE WHEN order_status = 'delivered' THEN gross_profit ELSE 0 END)
                   / NULLIF(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 0), 2) AS gross_margin_pct,
               SUM(returned_units) AS returned_units,
               ROUND(SUM(refund_amount), 2) AS refund_amount,
               ROUND(100.0 * SUM(returned_units)
                   / NULLIF(SUM(CASE WHEN order_status IN ('delivered','returned') THEN units ELSE 0 END), 0), 2) AS return_unit_rate_pct
        FROM vw_sales_detail
        GROUP BY category
        ORDER BY delivered_net_sales DESC
    """,
    "source_performance": """
        SELECT order_source,
               COUNT(*) AS total_orders,
               SUM(order_status = 'delivered') AS delivered_orders,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 2) AS delivered_net_sales,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END)
                   / NULLIF(SUM(order_status = 'delivered'), 0), 2) AS average_order_value,
               ROUND(100.0 * SUM(order_status = 'delivered') / COUNT(*), 2) AS delivered_share_pct
        FROM vw_order_analytics
        GROUP BY order_source
        ORDER BY delivered_net_sales DESC
    """,
    "payment_performance": """
        SELECT payment_method,
               COUNT(*) AS total_orders,
               SUM(order_status = 'delivered') AS delivered_orders,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 2) AS delivered_net_sales,
               ROUND(100.0 * SUM(order_status = 'delivered') / COUNT(*), 2) AS delivered_share_pct
        FROM vw_order_analytics
        GROUP BY payment_method
        ORDER BY delivered_net_sales DESC
    """,
    "device_performance": """
        SELECT device_type,
               COUNT(*) AS total_orders,
               SUM(order_status = 'delivered') AS delivered_orders,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 2) AS delivered_net_sales,
               ROUND(100.0 * SUM(order_status = 'delivered') / COUNT(*), 2) AS delivered_share_pct
        FROM vw_order_analytics
        GROUP BY device_type
        ORDER BY delivered_net_sales DESC
    """,
    "customer_segments": """
        SELECT age_group,
               gender,
               COUNT(DISTINCT CASE WHEN order_status = 'delivered' THEN customer_id END) AS delivered_customers,
               SUM(order_status = 'delivered') AS delivered_orders,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 2) AS delivered_net_sales,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END)
                   / NULLIF(SUM(order_status = 'delivered'), 0), 2) AS average_order_value
        FROM vw_order_analytics
        GROUP BY age_group, gender
        ORDER BY delivered_net_sales DESC
    """,
    "return_reasons": """
        SELECT return_reason,
               COUNT(DISTINCT return_id) AS return_records,
               SUM(return_quantity) AS returned_units,
               ROUND(SUM(refund_amount), 2) AS refund_amount,
               ROUND(100.0 * SUM(return_quantity) / SUM(SUM(return_quantity)) OVER (), 2) AS return_unit_share_pct
        FROM returns
        GROUP BY return_reason
        ORDER BY returned_units DESC
    """,
    "product_profitability": """
        SELECT product_id,
               product_name,
               category,
               segment,
               COUNT(DISTINCT CASE WHEN order_status = 'delivered' THEN order_id END) AS delivered_orders,
               SUM(CASE WHEN order_status = 'delivered' THEN units ELSE 0 END) AS delivered_units,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 2) AS delivered_net_sales,
               ROUND(SUM(CASE WHEN order_status = 'delivered' THEN gross_profit ELSE 0 END), 2) AS delivered_gross_profit,
               ROUND(100.0 * SUM(CASE WHEN order_status = 'delivered' THEN gross_profit ELSE 0 END)
                   / NULLIF(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 0), 2) AS gross_margin_pct,
               SUM(returned_units) AS returned_units,
               ROUND(SUM(refund_amount), 2) AS refund_amount
        FROM vw_sales_detail
        GROUP BY product_id, product_name, category, segment
        ORDER BY delivered_net_sales DESC
    """,
}


def import_csv(connection: sqlite3.Connection, table: str, source: Path) -> int:
    total = 0
    for chunk_number, chunk in enumerate(pd.read_csv(source, chunksize=100_000, low_memory=False)):
        mode = "replace" if chunk_number == 0 else "append"
        chunk.to_sql(table, connection, if_exists=mode, index=False)
        total += len(chunk)
    return total


def fetch_scalar(connection: sqlite3.Connection, sql: str) -> float:
    value = connection.execute(sql).fetchone()[0]
    return float(value or 0)


def build_kpis(connection: sqlite3.Connection) -> dict[str, float]:
    return {
        "total_orders": fetch_scalar(connection, "SELECT COUNT(*) FROM orders"),
        "delivered_orders": fetch_scalar(connection, "SELECT COUNT(*) FROM vw_order_analytics WHERE order_status='delivered'"),
        "delivered_net_sales": fetch_scalar(connection, "SELECT SUM(net_value) FROM vw_order_analytics WHERE order_status='delivered'"),
        "delivered_gross_profit": fetch_scalar(connection, "SELECT SUM(gross_profit) FROM vw_order_analytics WHERE order_status='delivered'"),
        "gross_margin_pct": fetch_scalar(connection, "SELECT 100.0*SUM(gross_profit)/SUM(net_value) FROM vw_order_analytics WHERE order_status='delivered'"),
        "average_order_value": fetch_scalar(connection, "SELECT SUM(net_value)/COUNT(*) FROM vw_order_analytics WHERE order_status='delivered'"),
        "delivered_units": fetch_scalar(connection, "SELECT SUM(units) FROM vw_order_analytics WHERE order_status='delivered'"),
        "returned_units": fetch_scalar(connection, "SELECT SUM(return_quantity) FROM returns"),
        "refund_amount": fetch_scalar(connection, "SELECT SUM(refund_amount) FROM returns"),
        "return_unit_rate_pct": fetch_scalar(connection, "SELECT 100.0*(SELECT SUM(return_quantity) FROM returns)/((SELECT SUM(units) FROM vw_order_analytics WHERE order_status='delivered')+(SELECT SUM(return_quantity) FROM returns))"),
        "cancellation_rate_pct": fetch_scalar(connection, "SELECT 100.0*AVG(order_status='cancelled') FROM orders"),
        "negative_margin_products": fetch_scalar(connection, "SELECT COUNT(*) FROM (SELECT product_id FROM vw_sales_detail WHERE order_status='delivered' GROUP BY product_id HAVING SUM(gross_profit)<0)"),
    }


def records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if TEMP_DATABASE_PATH.exists():
        TEMP_DATABASE_PATH.unlink()

    connection = sqlite3.connect(TEMP_DATABASE_PATH)
    try:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        for table, filename in SOURCE_FILES.items():
            count = import_csv(connection, table, SOURCE_DIR / filename)
            print(f"Imported {table}: {count:,} rows")
        for index_sql in INDEXES:
            connection.execute(index_sql)
        connection.executescript(VIEW_SQL)
        connection.execute("ANALYZE")

        frames: dict[str, pd.DataFrame] = {}
        for name, query in QUERIES.items():
            frame = pd.read_sql_query(query, connection)
            frame.to_csv(EXPORT_DIR / f"{name}.csv", index=False)
            frames[name] = frame

        fact = pd.read_sql_query("SELECT * FROM vw_sales_detail", connection)
        fact.to_csv(EXPORT_DIR / "powerbi_fact_sales.csv", index=False)

        date_min, date_max = connection.execute("SELECT MIN(order_date), MAX(order_date) FROM orders").fetchone()
        kpis = build_kpis(connection)
        kpi_frame = pd.DataFrame([{"metric": key, "value": value} for key, value in kpis.items()])
        kpi_frame.to_csv(EXPORT_DIR / "kpi_summary.csv", index=False)

        top_products = frames["product_profitability"].head(10)
        category_products = (
            frames["product_profitability"]
            .groupby("category", sort=False, group_keys=False)
            .head(10)
        )
        negative_products = frames["product_profitability"].query("delivered_gross_profit < 0")
        negative_margin_sales_share = (
            100.0 * negative_products["delivered_net_sales"].sum() / kpis["delivered_net_sales"]
        )
        kpis["negative_margin_sales_share_pct"] = float(negative_margin_sales_share)

        payload = {
            "meta": {
                "project": "Vietnam Fashion E-commerce Analytics",
                "date_min": date_min,
                "date_max": date_max,
                "source": str(SOURCE_DIR),
                "generated_from": "Clean pandas outputs, transformed with SQLite SQL",
            },
            "kpis": kpis,
            "monthly": records(frames["monthly_performance"]),
            "annual": records(frames["annual_performance"]),
            "categories": records(frames["category_performance"]),
            "sources": records(frames["source_performance"]),
            "payments": records(frames["payment_performance"]),
            "devices": records(frames["device_performance"]),
            "statuses": records(frames["status_summary"]),
            "returns": records(frames["return_reasons"]),
            "top_products": records(top_products),
            "category_products": records(category_products),
        }
        with (SITE_DATA_DIR / "dashboard-data.json").open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        connection.commit()
    finally:
        connection.close()

    os.replace(TEMP_DATABASE_PATH, DATABASE_PATH)
    print(f"Database: {DATABASE_PATH}")
    print(f"Exports: {EXPORT_DIR}")
    print(f"Site payload: {SITE_DATA_DIR / 'dashboard-data.json'}")


if __name__ == "__main__":
    main()
