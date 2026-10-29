SELECT
    COUNT(*) AS delivered_orders,
    ROUND(SUM(net_value), 2) AS delivered_net_sales,
    ROUND(SUM(gross_profit), 2) AS delivered_gross_profit,
    ROUND(100.0 * SUM(gross_profit) / SUM(net_value), 2) AS gross_margin_pct,
    ROUND(SUM(net_value) / COUNT(*), 2) AS average_order_value
FROM vw_order_analytics
WHERE order_status = 'delivered';

SELECT
    order_month,
    COUNT(*) AS total_orders,
    SUM(order_status = 'delivered') AS delivered_orders,
    ROUND(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 2)
        AS delivered_net_sales,
    ROUND(100.0 * SUM(CASE WHEN order_status = 'delivered' THEN gross_profit ELSE 0 END)
        / NULLIF(SUM(CASE WHEN order_status = 'delivered' THEN net_value ELSE 0 END), 0), 2)
        AS gross_margin_pct
FROM vw_order_analytics
GROUP BY order_month
ORDER BY order_month;

SELECT
    product_id,
    product_name,
    category,
    ROUND(SUM(net_value), 2) AS delivered_net_sales,
    ROUND(SUM(gross_profit), 2) AS delivered_gross_profit,
    ROUND(100.0 * SUM(gross_profit) / NULLIF(SUM(net_value), 0), 2) AS gross_margin_pct
FROM vw_sales_detail
WHERE order_status = 'delivered'
GROUP BY product_id, product_name, category
HAVING SUM(gross_profit) < 0
ORDER BY delivered_net_sales DESC;

SELECT
    return_reason,
    SUM(return_quantity) AS returned_units,
    ROUND(SUM(refund_amount), 2) AS refund_amount,
    ROUND(100.0 * SUM(return_quantity) / SUM(SUM(return_quantity)) OVER (), 2)
        AS return_unit_share_pct
FROM returns
GROUP BY return_reason
ORDER BY returned_units DESC;

SELECT
    (SELECT COUNT(*) FROM order_items) AS source_rows,
    (SELECT COUNT(*)
       FROM order_items AS oi
       JOIN orders AS o ON o.order_id = oi.order_id) AS rows_after_join;
