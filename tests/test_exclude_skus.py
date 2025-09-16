import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shopify_tool import packing_lists


def test_exclude_skus_from_packing_list(tmp_path):
    """
    Tests that the create_packing_list function correctly excludes specified
    "virtual" SKUs from the final report.
    """
    # 1. Create a sample analysis DataFrame
    analysis_df = pd.DataFrame(
        {
            "Order_Fulfillment_Status": ["Fulfillable", "Fulfillable", "Fulfillable", "Fulfillable"],
            "Order_Number": ["1001", "1001", "1002", "1003"],
            "SKU": ["ABC-123", "Shipping protection", "XYZ-456", "07"],
            "Product_Name": ["Real Product A", "Virtual Item", "Real Product B", "Another Virtual Item"],
            "Quantity": [1, 1, 1, 1],
            "Shipping_Provider": ["DHL", "DHL", "DPD", "PostOne"],
            "Destination_Country": ["BG", "BG", "US", "DE"],
        }
    )

    # 2. Define the SKUs to exclude and the output path
    skus_to_exclude = ["07", "Shipping protection"]
    output_file = tmp_path / "packing_list_excluded.xlsx"

    # 3. Call the function to generate the packing list
    packing_lists.create_packing_list(
        analysis_df=analysis_df,
        output_file=str(output_file),
        report_name="TestExcludeSKUs",
        filters=None,
        exclude_skus=skus_to_exclude,
    )

    # 4. Assert that the output file was created
    assert os.path.exists(output_file)

    # 5. Read the generated Excel file and validate its contents
    result_df = pd.read_excel(output_file)

    # Get the list of SKUs present in the output report
    # The column name in the output is 'SKU' as defined in columns_for_print
    output_skus = result_df["SKU"].tolist()

    # 6. Assert that the excluded SKUs are NOT in the output
    assert "Shipping protection" not in output_skus
    assert "07" not in output_skus

    # 7. Assert that the real SKUs ARE in the output
    assert "ABC-123" in output_skus
    assert "XYZ-456" in output_skus

    # 8. Assert the final length is correct
    assert len(output_skus) == 2
