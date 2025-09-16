import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shopify_tool import core


def run_test(stock_df, orders_df, history_df=None, low_stock_threshold=10):
    """Helper function to run an analysis with given data and return the results."""
    config = {"settings": {"low_stock_threshold": low_stock_threshold}}
    config["test_stock_df"] = stock_df
    config["test_orders_df"] = orders_df
    config["test_history_df"] = history_df if history_df is not None else pd.DataFrame({"Order_Number": []})
    success, _, final_df, stats = core.run_full_analysis(None, None, None, ";", config)
    assert success
    return final_df, stats


def test_TC02_multi_item_fulfillable():
    """Tests a multi-item order where all items are in stock."""
    # One multi-item order, all items available
    stock = pd.DataFrame({"Артикул": ["A", "B"], "Име": ["A", "B"], "Наличност": [2, 2]})
    orders = pd.DataFrame(
        {
            "Name": ["M1", "M1"],
            "Lineitem sku": ["A", "B"],
            "Lineitem quantity": [1, 1],
            "Shipping Method": ["dhl", "dhl"],
            "Shipping Country": ["BG", "BG"],
            "Tags": ["", ""],
            "Notes": ["", ""],
        }
    )
    final_df, _ = run_test(stock, orders)
    assert final_df["Order_Fulfillment_Status"].unique().tolist() == ["Fulfillable"]
    # Final stock reduced
    a_final = final_df[final_df["SKU"] == "A"]["Final_Stock"].iloc[0]
    b_final = final_df[final_df["SKU"] == "B"]["Final_Stock"].iloc[0]
    assert a_final == 1 and b_final == 1


def test_TC03_prioritization_multi_over_single():
    """Tests that a multi-item order is prioritized over a single-item order."""
    # Stock A=2, B=1
    stock = pd.DataFrame({"Артикул": ["A", "B"], "Име": ["A", "B"], "Наличност": [2, 1]})
    # Multi-order M1 wants A:2 & B:1 (item_count=2); Single S1 wants A:1
    orders = pd.DataFrame(
        {
            "Name": ["M1", "M1", "S1"],
            "Lineitem sku": ["A", "B", "A"],
            "Lineitem quantity": [2, 1, 1],
            "Shipping Method": ["dhl", "dhl", "dpd"],
            "Shipping Country": ["BG", "BG", "BG"],
            "Tags": ["", "", ""],
            "Notes": ["", "", ""],
        }
    )
    final_df, _ = run_test(stock, orders)
    # M1 should be Fulfillable, S1 Not Fulfillable
    status_M1 = final_df[final_df["Order_Number"] == "M1"]["Order_Fulfillment_Status"].iloc[0]
    status_S1 = final_df[final_df["Order_Number"] == "S1"]["Order_Fulfillment_Status"].iloc[0]
    assert status_M1 == "Fulfillable"
    assert status_S1 == "Not Fulfillable"


def test_TC05_multi_order_with_missing_item_fails():
    """Tests that a multi-item order fails if any single item is out of stock."""
    # Multi-order with one missing SKU -> whole order Not Fulfillable
    stock = pd.DataFrame({"Артикул": ["A"], "Име": ["A"], "Наличност": [5]})
    orders = pd.DataFrame(
        {
            "Name": ["M1", "M1"],
            "Lineitem sku": ["A", "C"],
            "Lineitem quantity": [1, 1],
            "Shipping Method": ["dhl", "dhl"],
            "Shipping Country": ["BG", "BG"],
            "Tags": ["", ""],
            "Notes": ["", ""],
        }
    )
    final_df, _ = run_test(stock, orders)
    # Entire M1 should be Not Fulfillable
    assert final_df[final_df["Order_Number"] == "M1"]["Order_Fulfillment_Status"].unique().tolist() == [
        "Not Fulfillable"
    ]
    # Ensure stock for A not reduced
    a_final = final_df[final_df["SKU"] == "A"]["Final_Stock"].iloc[0]
    assert a_final == 5


def test_TC08_exact_stock_matches():
    """Tests fulfillment when the required quantity exactly matches the available stock."""
    stock = pd.DataFrame({"Артикул": ["X"], "Име": ["X"], "Наличност": [1]})
    orders = pd.DataFrame(
        {
            "Name": ["O1"],
            "Lineitem sku": ["X"],
            "Lineitem quantity": [1],
            "Shipping Method": ["dpd"],
            "Shipping Country": ["BG"],
            "Tags": [""],
            "Notes": [""],
        }
    )
    final_df, _ = run_test(stock, orders)
    assert final_df["Order_Fulfillment_Status"].iloc[0] == "Fulfillable"
    assert final_df["Final_Stock"].iloc[0] == 0


def test_TC09_missing_lineitem_sku_is_ignored():
    """Tests that order line items with a missing SKU are ignored."""
    stock = pd.DataFrame({"Артикул": ["Y"], "Име": ["Y"], "Наличност": [5]})
    orders = pd.DataFrame(
        {
            "Name": ["O1", "O2"],
            "Lineitem sku": ["Y", pd.NA],
            "Lineitem quantity": [1, 1],
            "Shipping Method": ["dhl", "dhl"],
            "Shipping Country": ["BG", "BG"],
            "Tags": ["", ""],
            "Notes": ["", ""],
        }
    )
    final_df, _ = run_test(stock, orders)
    # Only O1 should be present in final_df
    assert "O2" not in final_df["Order_Number"].unique()


def test_TC10_missing_sku_in_stock_file():
    """Tests that stock items with a missing SKU are ignored."""
    # Stock has a row with missing SKU which should be ignored
    stock = pd.DataFrame({"Артикул": [pd.NA], "Име": ["NA"], "Наличност": [99]})
    orders = pd.DataFrame(
        {
            "Name": ["O1"],
            "Lineitem sku": ["Z"],
            "Lineitem quantity": [1],
            "Shipping Method": ["dpd"],
            "Shipping Country": ["BG"],
            "Tags": [""],
            "Notes": [""],
        }
    )
    final_df, _ = run_test(stock, orders)
    # SKU Z not found -> Not Fulfillable
    assert final_df["Order_Fulfillment_Status"].iloc[0] == "Not Fulfillable"


def test_TC11_duplicate_sku_in_stock_keep_first():
    """Tests that duplicate SKUs in the stock file are handled by keeping the first entry."""
    stock = pd.DataFrame({"Артикул": ["D", "D"], "Име": ["D1", "D2"], "Наличност": [5, 99]})
    orders = pd.DataFrame(
        {
            "Name": ["O1"],
            "Lineitem sku": ["D"],
            "Lineitem quantity": [6],
            "Shipping Method": ["dhl"],
            "Shipping Country": ["BG"],
            "Tags": [""],
            "Notes": [""],
        }
    )
    final_df, _ = run_test(stock, orders)
    # Because keep='first', available stock is 5 -> Not Fulfillable
    assert final_df["Order_Fulfillment_Status"].iloc[0] == "Not Fulfillable"


def test_TC13_empty_input_files_do_not_crash():
    """Tests that the analysis runs without crashing when given empty input files."""
    stock = pd.DataFrame(columns=["Артикул", "Име", "Наличност"])
    orders = pd.DataFrame(
        columns=["Name", "Lineitem sku", "Lineitem quantity", "Shipping Method", "Shipping Country", "Tags", "Notes"]
    )
    final_df, stats = run_test(stock, orders)
    assert final_df.empty
    # stats may be zeros or None; ensure function returned a valid stats dict
    assert isinstance(stats, dict)
