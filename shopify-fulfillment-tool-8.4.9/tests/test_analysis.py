import pytest
import pandas as pd
import sys
import os

# Add the project root to the Python path to allow for correct module imports
# This ensures that we can import from the 'shopify_tool' package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shopify_tool.analysis import _generalize_shipping_method, run_analysis, toggle_order_fulfillment


# Test cases for the _generalize_shipping_method function
# We use @pytest.mark.parametrize to run the same test with different inputs and expected outputs.
# This is an efficient way to test multiple scenarios.
@pytest.mark.parametrize(
    "input_method, expected_output",
    [
        ("dhl express", "DHL"),
        ("some other dhl service", "DHL"),
        ("DPD Standard", "DPD"),
        ("dpd", "DPD"),
        ("international shipping", "PostOne"),
        ("Some Custom Method", "Some Custom Method"),
        ("unknown", "Unknown"),
        (None, "Unknown"),
        (pd.NA, "Unknown"),
        ("", "Unknown"),  # An empty string should be handled as 'Unknown'
    ],
)
def test_generalize_shipping_method(input_method, expected_output):
    """
    Tests the _generalize_shipping_method function with various inputs.

    Args:
        input_method (str or None): The raw shipping method string to test.
        expected_output (str): The expected standardized string.
    """
    # The assert statement checks if the function's output matches the expected output.
    # If they don't match, pytest will report a failure.
    assert _generalize_shipping_method(input_method) == expected_output


def test_fulfillment_prioritization_logic():
    """Tests that the fulfillment logic correctly prioritizes multi-item orders."""
    # Create a stock of 4 for a single SKU. This is the key to the test.
    # It's enough to fulfill the two multi-item orders (2+2=4), but not any of the single-item orders.
    stock_df = pd.DataFrame({"Артикул": ["SKU-1"], "Име": ["Test Product"], "Наличност": [4]})

    # Create four orders for the same SKU with different priorities
    # Order 1001: Older, Multi-item (2 items) - Priority 1
    # Order 1002: Newer, Multi-item (2 items) - Priority 2
    # Order 1003: Older, Single-item (1 item) - Priority 3
    # Order 1004: Newer, Single-item (1 item) - Priority 4
    orders_df = pd.DataFrame(
        {
            "Name": ["1002", "1002", "1001", "1001", "1004", "1003"],
            "Lineitem sku": ["SKU-1", "SKU-1", "SKU-1", "SKU-1", "SKU-1", "SKU-1"],
            "Lineitem quantity": [1, 1, 1, 1, 1, 1],  # Each row is one item
            "Shipping Method": ["dhl"] * 6,
            "Shipping Country": ["BG"] * 6,
            "Tags": [""] * 6,
            "Notes": [""] * 6,
        }
    )

    # Empty history
    history_df = pd.DataFrame(columns=["Order_Number", "Execution_Date"])

    # With stock of 5, only the two multi-item orders should be fulfilled (2+2=4 items)
    # The single-item orders should not be fulfilled.
    final_df, _, _, _ = run_analysis(stock_df, orders_df, history_df)

    # Check status of each order
    status_map = final_df.drop_duplicates(subset=["Order_Number"]).set_index("Order_Number")["Order_Fulfillment_Status"]

    assert status_map["1001"] == "Fulfillable"  # Priority 1
    assert status_map["1002"] == "Fulfillable"  # Priority 2
    assert status_map["1003"] == "Not Fulfillable"  # Priority 3
    assert status_map["1004"] == "Not Fulfillable"  # Priority 4


def test_summary_missing_report():
    """Tests that the missing items summary is correctly generated."""
    stock_df = pd.DataFrame({"Артикул": ["SKU-1"], "Име": ["P1"], "Наличност": [5]})
    orders_df = pd.DataFrame(
        {
            "Name": ["1001"],
            "Lineitem sku": ["SKU-1"],
            "Lineitem quantity": [10],  # Require 10, but only 5 are in stock
            "Shipping Method": ["dhl"],
            "Shipping Country": ["BG"],
            "Tags": [""],
            "Notes": [""],
        }
    )
    history_df = pd.DataFrame(columns=["Order_Number", "Execution_Date"])

    _, _, summary_missing_df, _ = run_analysis(stock_df, orders_df, history_df)

    assert not summary_missing_df.empty
    assert len(summary_missing_df) == 1
    assert summary_missing_df.iloc[0]["SKU"] == "SKU-1"
    assert summary_missing_df.iloc[0]["Total Quantity"] == 10


@pytest.fixture
def sample_analysis_df():
    """Provides a sample analysis DataFrame fixture for testing."""
    df = pd.DataFrame(
        {
            "Order_Number": ["1001", "1001", "1002"],
            "SKU": ["SKU-A", "SKU-B", "SKU-A"],
            "Quantity": [1, 2, 3],
            "Stock": [10, 10, 10],
            "Final_Stock": [6, 8, 6],  # Note: Both SKU-A rows have the same final stock initially
            "Order_Fulfillment_Status": ["Fulfillable", "Fulfillable", "Not Fulfillable"],
        }
    )
    # Ensure all rows for a given SKU start with the same Final_Stock
    df["Final_Stock"] = df.groupby("SKU")["Final_Stock"].transform("first")
    return df


class TestToggleOrderFulfillment:
    """Groups tests for the toggle_order_fulfillment function."""

    def test_toggle_fulfillable_to_not_fulfillable(self, sample_analysis_df):
        """Tests changing an order from 'Fulfillable' to 'Not Fulfillable'."""
        df = sample_analysis_df.copy()

        # Un-fulfill order 1001 (contains SKU-A:1, SKU-B:2)
        success, _, updated_df = toggle_order_fulfillment(df, "1001")

        assert success
        # Stock for SKU-A (6) should increase by 1 -> 7. This affects all SKU-A rows.
        # Stock for SKU-B (8) should increase by 2 -> 10.
        assert all(updated_df[updated_df["SKU"] == "SKU-A"]["Final_Stock"] == 7)
        assert all(updated_df[updated_df["SKU"] == "SKU-B"]["Final_Stock"] == 10)
        assert all(updated_df[updated_df["Order_Number"] == "1001"]["Order_Fulfillment_Status"] == "Not Fulfillable")

    def test_toggle_not_fulfillable_to_fulfillable_success(self, sample_analysis_df):
        """Tests successfully changing an order to 'Fulfillable' when stock is sufficient."""
        df = sample_analysis_df.copy()
        # Stock for SKU-A is 6. Order 1002 needs 3. This should succeed.

        success, _, updated_df = toggle_order_fulfillment(df, "1002")

        assert success
        # Stock for SKU-A (6) should decrease by 3 -> 3. This affects all SKU-A rows.
        assert all(updated_df[updated_df["SKU"] == "SKU-A"]["Final_Stock"] == 3)
        assert all(updated_df[updated_df["Order_Number"] == "1002"]["Order_Fulfillment_Status"] == "Fulfillable")

    def test_toggle_not_fulfillable_to_fulfillable_fail_no_stock(self, sample_analysis_df):
        """Tests that changing an order to 'Fulfillable' fails when stock is insufficient."""
        df = sample_analysis_df.copy()
        # Order 1002 needs 3 of SKU-A, but let's set the stock to 2
        df.loc[df["SKU"] == "SKU-A", "Final_Stock"] = 2

        success, error_msg, updated_df = toggle_order_fulfillment(df, "1002")

        assert not success
        assert "Insufficient stock" in error_msg
        # The dataframe should not have been changed
        assert all(updated_df[updated_df["SKU"] == "SKU-A"]["Final_Stock"] == 2)
        assert all(updated_df[updated_df["Order_Number"] == "1002"]["Order_Fulfillment_Status"] == "Not Fulfillable")
