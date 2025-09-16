import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shopify_tool import packing_lists


def test_create_packing_list_minimal(tmp_path):
    """Tests the basic creation of a packing list with minimal data."""
    # Build a small DataFrame that matches the analysis_df shape
    df = pd.DataFrame(
        {
            "Order_Fulfillment_Status": ["Fulfillable", "Fulfillable"],
            "Order_Number": ["A1", "A1"],
            "SKU": ["S1", "S2"],
            "Product_Name": ["P1", "P2"],
            "Quantity": [1, 2],
            "Shipping_Provider": ["DHL", "DHL"],
            "Destination_Country": ["BG", ""],
        }
    )

    out_file = tmp_path / "packing_test.xlsx"
    packing_lists.create_packing_list(df, str(out_file), report_name="TestReport", filters=None)
    assert out_file.exists()


def test_create_packing_list_with_not_equals_filter(tmp_path):
    """
    Tests that a packing list can be correctly filtered with a '!=' operator.
    """
    # Build a DataFrame with different shipping providers
    df = pd.DataFrame(
        {
            "Order_Fulfillment_Status": ["Fulfillable", "Fulfillable", "Fulfillable", "Fulfillable", "Not Fulfillable"],
            "Order_Number": ["A1", "A2", "A3", "A4", "A5"],
            "SKU": ["S1", "S2", "S3", "S4", "S5"],
            "Product_Name": ["P1", "P2", "P3", "P4", "P5"],
            "Quantity": [1, 1, 1, 1, 1],
            "Shipping_Provider": ["DHL", "PostOne", "DPD", "DHL", "DHL"],
            "Destination_Country": ["BG", "US", "DE", "FR", "CA"],
        }
    )

    out_file = tmp_path / "packing_test_ne.xlsx"

    # Define a filter to exclude DHL
    filters = [{"field": "Shipping_Provider", "operator": "!=", "value": "DHL"}]

    packing_lists.create_packing_list(df, str(out_file), report_name="TestReportNE", filters=filters)

    assert out_file.exists()

    # Read the generated Excel file and verify its contents
    result_df = pd.read_excel(out_file)

    # The output should only contain the 'PostOne' and 'DPD' orders
    assert len(result_df) == 2
    assert "A2" in result_df["Order_Number"].values
    assert "A3" in result_df["Order_Number"].values
    assert "A1" not in result_df["Order_Number"].values
    assert "A4" not in result_df["Order_Number"].values
    assert "A5" not in result_df["Order_Number"].values  # Should be excluded due to status
