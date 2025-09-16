import sys
import os
import pandas as pd

# Додаємо корінь проекту у sys.path для коректного імпорту
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def make_test_data():
    """Creates a sample set of DataFrames and config for testing run_analysis."""
    # Stock: 2 items, one with zero stock
    stock_df = pd.DataFrame({"Артикул": ["SKU1", "SKU2"], "Име": ["Product 1", "Product 2"], "Наличност": [5, 0]})
    # Orders: 2 orders, one fulfillable, one not
    orders_df = pd.DataFrame(
        {
            "Name": ["Order1", "Order2"],
            "Lineitem sku": ["SKU1", "SKU2"],
            "Lineitem quantity": [3, 2],
            "Shipping Method": ["dhl express", "DPD Standard"],
            "Shipping Country": ["BG", "RO"],
            "Tags": ["", ""],
            "Notes": ["", ""],
        }
    )
    # History: empty for simplicity
    history_df = pd.DataFrame({"Order_Number": []})
    # Config with low_stock_threshold
    config = {"settings": {"low_stock_threshold": 10, "stock_csv_delimiter": ";"}}
    # Attach DataFrames to config for test mode
    config["test_stock_df"] = stock_df
    config["test_orders_df"] = orders_df
    config["test_history_df"] = history_df
    return stock_df, orders_df, history_df, config


def test_run_analysis_basic():
    """Tests the basic execution of run_full_analysis in test mode."""
    from shopify_tool import core

    stock_df, orders_df, history_df, config = make_test_data()
    # Use core.run_full_analysis to test new logic
    success, _, final_df, stats = core.run_full_analysis(
        stock_file_path=None, orders_file_path=None, output_dir_path=None, stock_delimiter=";", config=config
    )
    assert success
    # Check fulfillment status
    assert final_df.loc[final_df["Order_Number"] == "Order1", "Order_Fulfillment_Status"].iloc[0] == "Fulfillable"
    assert final_df.loc[final_df["Order_Number"] == "Order2", "Order_Fulfillment_Status"].iloc[0] == "Not Fulfillable"
    # Check Stock_Alert logic
    assert final_df.loc[final_df["SKU"] == "SKU1", "Stock_Alert"].iloc[0] == "Low Stock"
    assert final_df.loc[final_df["SKU"] == "SKU2", "Stock_Alert"].iloc[0] == "Low Stock"
