import os
import sys
from pathlib import Path

import pandas as pd


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = Path(os.environ.get("VN_FASHION_RAW_DIR", PROJECT_DIR / "data" / "raw"))
CLEAN_DIR = Path(os.environ.get("VN_FASHION_CLEAN_DIR", PROJECT_DIR / "data" / "cleaned"))
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

customers=pd.read_csv(RAW_DIR / "customers.csv")
orders=pd.read_csv(RAW_DIR / "orders.csv")
order_items=pd.read_csv(RAW_DIR / "order_items.csv",dtype={"promo_id_2":"string"},low_memory=False)
products=pd.read_csv(RAW_DIR / "products.csv")
returns=pd.read_csv(RAW_DIR / "returns.csv")



print ("customer_id trùng",customers["customer_id"].duplicated().sum())
print("order_id Trùng",orders["order_id"].duplicated().sum())
print ("product_id trùng",products["product_id"].duplicated().sum())
print("return_id trùng:", returns["return_id"].duplicated().sum())
print("order_items trùng toàn bộ dòng",order_items.duplicated().sum())
print("cặp order_id + product_id trùng",order_items.duplicated(subset=["order_id","product_id"]).sum())
    
duplicate_check=order_items[order_items.duplicated(subset=["product_id","order_id"],keep=False)].sort_values(["product_id","order_id"])
print (duplicate_check)

orders["order_date"] = pd.to_datetime(orders["order_date"],format="%Y-%m-%d",errors="coerce")
print(orders["order_date"].head(5))
print(orders["order_date"].dtypes)
print(orders["order_date"].min())
print(orders["order_date"].max())	
print("Ngày lỗi:", orders["order_date"].isna().sum())
ngayloi= orders["order_date"].isna()

print (orders["order_status"].value_counts(dropna=False))
orders["order_status"] = (orders["order_status"].str.strip().str.lower())

print (orders["payment_method"].value_counts(dropna=False))
orders["payment_method"]= orders["payment_method"].str.strip().str.lower()
orders["device_type"]=orders["device_type"].str.strip().str.lower()
print (orders["device_type"].value_counts(dropna=False))
print (orders["order_source"].value_counts(dropna=False))
orders ["order_source"]= orders["order_source"].str.strip().str.lower()

number_column=order_items[["quantity","unit_price","discount_amount"]]
print (number_column.dtypes)
print (number_column.isna().sum())
print (number_column.min())
print (number_column.max())

order_items["line_value"]=order_items["quantity"]*order_items["unit_price"]
order_items["net_value"]=order_items["line_value"]-order_items["discount_amount"]
check_columns= order_items[["quantity","unit_price","discount_amount","line_value","net_value"]]
print (check_columns.head(3))
print (check_columns.min())
print (check_columns.max())
print ("check_xem_netvalue_negative?",(order_items["net_value"]<0).sum())


invalid_mask = ((order_items["quantity"] <= 0)
    | (order_items["unit_price"] <= 0)
    | (order_items["discount_amount"] < 0)
    | (order_items["net_value"] < 0))
invalid_items = order_items[invalid_mask]

print(
    invalid_items[
        [
            "order_id",
            "product_id",
            "quantity",
            "unit_price",
            "discount_amount",
            "line_value",
            "net_value"
        ]
    ].head(5)
)


sales=order_items.merge(orders[["order_id","customer_id","order_status","order_date"]],on="order_id",how="left",validate="many_to_one")
print("Trước merge:", order_items.shape)
print("Sau merge:", sales.shape)
print("Order items không tìm thấy order:",sales["order_status"].isna().sum())

       
delivered_sale=sales[sales["order_status"] == "delivered"].copy()
print("Tất cả dòng sản phẩm:",sales.shape)
print("Dòng sản phẩm delivered:",delivered_sale.shape)
print(delivered_sale.head())
delivered_value = delivered_sale["net_value"].sum()

total_orders= delivered_sale["order_id"].nunique()

total_customers = delivered_sale["customer_id"].nunique()

total_units = delivered_sale["quantity"].sum()

aov = delivered_value / total_orders

print("Delivered value:", delivered_value)
print("Total orders:", total_orders)
print("Total customers:", total_customers)
print("Total units:", total_units)
print("AOV:", aov)

delivered_sale["year_month"]=delivered_sale["order_date"].dt.to_period("M")
monthly_value=delivered_sale.groupby("year_month")["net_value"].sum().reset_index()
print (monthly_value)
monthly_summary=delivered_sale.groupby("year_month").agg(total_orders=("order_id","nunique"),total_customers=("customer_id","nunique"),total_units=("quantity","sum"),delivered_value=("net_value","sum")).reset_index()
monthly_summary["aov"] =  monthly_summary["delivered_value"] / monthly_summary["total_orders"]

print(monthly_summary.head(12))

sale_product=delivered_sale.merge(products[["product_id","product_name","category","segment"]],on="product_id",how="left",validate="many_to_one")
print("Dòng bán không tìm thấy category:",sale_product["category"].isna().sum())
product_summary=sale_product.groupby(["product_id", "product_name", "category"]).agg(total_orders=("order_id","nunique"),total_units=("quantity","sum"),delivered_value=("net_value","sum")).reset_index().sort_values(
"delivered_value",ascending=False)
print (product_summary.head(10))
returns["return_date"]=pd.to_datetime(returns["return_date"],format="%Y-%m-%d",errors="coerce")
returns["return_reason"]= returns["return_reason"].str.lower().str.strip()
print("Ngày hoàn lỗi:", returns["return_date"].isna().sum())

print( returns["return_reason"].value_counts(dropna=False))
return_reason_summary=returns.groupby("return_reason").agg(return_records=("return_id","nunique"),returned_units=("return_quantity","sum"),refund_amount=("refund_amount","sum")).sort_values("refund_amount",ascending=False).reset_index()
print(return_reason_summary)
returns_product = returns.merge( products[ [  "product_id",  "category"]],on="product_id",how="left", validate="many_to_one")
print("Trước merge:", returns.shape)
print("Sau merge:", returns_product.shape)

print(
    "Không tìm thấy category:",
    returns_product["category"].isna().sum()
)
category_returns = (
    returns_product
    .groupby("category")
    .agg(
        return_records=("return_id", "nunique"),
        returned_units=("return_quantity", "sum"),
        refund_amount=("refund_amount", "sum")
    )
    .reset_index()
    .sort_values(
        "refund_amount",
        ascending=False
    )
)
category_summary = (
    sale_product
    .groupby("category")
    .agg(
        total_orders=("order_id", "nunique"),
        total_units=("quantity", "sum"),
        delivered_value=("net_value", "sum")
    )
    .reset_index()
)
print("category_summaryy",category_summary.head())
print(category_returns.head())
print(category_returns)
category_performance = category_summary.merge(
    category_returns,
    on="category",
    how="left"
)
return_columns = [
    "return_records",
    "returned_units",
    "refund_amount"
]

category_performance[return_columns] = (
    category_performance[return_columns]
    .fillna(0)
)

category_performance["total_processed_units"] = category_performance["total_units"] + category_performance["returned_units"]
category_performance["return_rate_pct"] = (
    category_performance["returned_units"]
    / category_performance["total_processed_units"]
    * 100
)
category_performance = (
    category_performance
    .sort_values(
        "return_rate_pct",
        ascending=False
    )
)
print(category_performance)


output_folder = CLEAN_DIR
customers.to_csv(
    output_folder / "customers_clean.csv",
    index=False
)

orders.to_csv(
    output_folder / "orders_clean.csv",
    index=False
)

order_items.to_csv(
    output_folder / "order_items_clean.csv",
    index=False
)

products.to_csv(
    output_folder / "products_clean.csv",
    index=False
)

returns.to_csv(
    output_folder / "returns_clean.csv",
    index=False
)

monthly_summary.to_csv(
    output_folder / "monthly_summary.csv",
    index=False
)

category_performance.to_csv(
    output_folder / "category_performance.csv",
    index=False
)

product_summary.head(10).to_csv(
    output_folder / "top_10_products.csv",
    index=False
)

return_reason_summary.to_csv(
    output_folder / "return_reason_summary.csv",
    index=False
)

print("Đã xuất xong")
