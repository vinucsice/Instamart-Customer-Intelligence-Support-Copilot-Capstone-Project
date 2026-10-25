-- sql/queries.sql — Part A, task 6: the seven business questions against data/instamart.db.
-- Unless stated otherwise only completed orders count as revenue or spend.
-- Each block is one statement; pipeline/a_sql.py splits on the semicolons and runs each
-- with pd.read_sql_query, asserting the reference result for every query.

-- Q1: WHERE then HAVING — customers whose total of completed orders above INR 500 exceeds INR 8000.
SELECT o.customer_id, SUM(o.order_amount) AS big_order_total
FROM orders o
WHERE o.status = 'completed' AND o.order_amount > 500
GROUP BY o.customer_id
HAVING SUM(o.order_amount) > 8000
ORDER BY big_order_total DESC;

-- Q2: three-table join — completed revenue by city and product category.
SELECT c.city, p.category, SUM(o.order_amount) AS revenue
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN products p ON p.product_id = o.product_id
WHERE o.status = 'completed'
GROUP BY c.city, p.category
ORDER BY revenue DESC;

-- Q3: scalar subquery — products priced above the average catalogue price.
SELECT product_id, product_name, category, price_inr
FROM products
WHERE price_inr > (SELECT AVG(price_inr) FROM products)
ORDER BY price_inr DESC;

-- Q4: LEFT JOIN — customers who have no completed order.
SELECT c.customer_id, c.city
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.customer_id AND o.status = 'completed'
WHERE o.order_id IS NULL
ORDER BY c.customer_id;

-- Q5: common table expressions — customers whose completed spend is above the average
-- of the per-customer completed spend totals.
WITH spend AS (
    SELECT customer_id, SUM(order_amount) AS total_spend
    FROM orders
    WHERE status = 'completed'
    GROUP BY customer_id
),
avg_spend AS (
    SELECT AVG(total_spend) AS avg_total_spend FROM spend
)
SELECT s.customer_id, s.total_spend, ROUND(a.avg_total_spend, 2) AS avg_total_spend
FROM spend s
CROSS JOIN avg_spend a
WHERE s.total_spend > a.avg_total_spend
ORDER BY s.total_spend DESC;

-- Q6: ranking window functions — RANK, DENSE_RANK and ROW_NUMBER of every customer with
-- completed spend, partitioned by city and ordered by total spend descending.
WITH spend AS (
    SELECT o.customer_id, c.city, SUM(o.order_amount) AS total_spend
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.status = 'completed'
    GROUP BY o.customer_id, c.city
)
SELECT customer_id, city, total_spend,
       RANK() OVER (PARTITION BY city ORDER BY total_spend DESC) AS rnk,
       DENSE_RANK() OVER (PARTITION BY city ORDER BY total_spend DESC) AS dense_rnk,
       ROW_NUMBER() OVER (PARTITION BY city ORDER BY total_spend DESC) AS row_num
FROM spend
ORDER BY city, rnk, customer_id;

-- Q7: running total — daily completed revenue with a cumulative sum ordered by day.
SELECT SUBSTR(order_ts, 1, 10) AS day,
       SUM(order_amount) AS revenue,
       SUM(SUM(order_amount)) OVER (ORDER BY SUBSTR(order_ts, 1, 10)) AS cumulative_revenue
FROM orders
WHERE status = 'completed'
GROUP BY SUBSTR(order_ts, 1, 10)
ORDER BY day;
