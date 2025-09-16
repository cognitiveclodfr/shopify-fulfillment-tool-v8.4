import sys
import os
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shopify_tool import core


def make_stock_df():
    """Creates a sample stock DataFrame for testing."""
    return pd.DataFrame({"Артикул": ["02-FACE-1001", "SKU-2"], "Име": ["Mask A", "Item 2"], "Наличност": [5, 10]})


def make_orders_df():
    """Creates a sample orders DataFrame for testing."""
    return pd.DataFrame(
        {
            "Name": ["1001", "1002"],
            "Lineitem sku": ["02-FACE-1001", "SKU-2"],
            "Lineitem quantity": [2, 1],
            "Shipping Method": ["dhl", "dpd"],
            "Shipping Country": ["BG", "BG"],
            "Tags": ["", ""],
            "Notes": ["", ""],
        }
    )


def test_run_full_analysis_basic():
    """Tests the basic in-memory execution of run_full_analysis."""
    stock_df = make_stock_df()
    orders_df = make_orders_df()
    # set threshold to 4 so final stock 3 will be flagged as Low Stock
    config = {"settings": {"low_stock_threshold": 4}, "tagging_rules": {}}
    # inject test dfs
    config["test_stock_df"] = stock_df
    config["test_orders_df"] = orders_df
    config["test_history_df"] = pd.DataFrame({"Order_Number": []})

    success, output_path, final_df, stats = core.run_full_analysis(None, None, None, ";", config)
    assert success
    assert output_path is None
    assert "Final_Stock" in final_df.columns
    # low stock alert should appear for SKU with final stock below threshold
    mask_rows = final_df[final_df["SKU"] == "02-FACE-1001"]
    assert any(mask_rows["Stock_Alert"].str.contains("Low Stock"))


def test_full_run_with_file_io(tmp_path):
    """
    An integration-style test for the core module that uses the file system.
    """
    # 1. Setup temporary file structure
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    # 2. Create mock input files
    stock_df = make_stock_df()
    stock_file = tmp_path / "stock.csv"
    stock_df.to_csv(stock_file, index=False, sep=";")

    orders_df = make_orders_df()
    orders_file = tmp_path / "orders.csv"
    orders_df.to_csv(orders_file, index=False)

    # 3. Create a config dictionary pointing to our temp files
    config = {
        "settings": {"stock_csv_delimiter": ";", "low_stock_threshold": 4},
        "column_mappings": {"orders_required": ["Name", "Lineitem sku"], "stock_required": ["Артикул", "Наличност"]},
        "rules": [],
        "packing_lists": [{"name": "Test Packing List", "output_filename": "test_packing_list.xlsx", "filters": []}],
        "stock_exports": [{"name": "Test Stock Export", "output_filename": "test_stock_export.xls", "filters": []}],
    }

    # 4. Run the main analysis function
    success, analysis_path, final_df, stats = core.run_full_analysis(
        str(stock_file), str(orders_file), str(output_dir), ";", config
    )

    # 5. Assert main analysis results
    assert success
    assert os.path.exists(analysis_path)
    assert "fulfillment_analysis.xlsx" in analysis_path

    # 6. Run report generation functions
    # Packing List
    packing_report_config = config["packing_lists"][0]
    packing_report_config["output_filename"] = str(output_dir / packing_report_config["output_filename"])
    pack_success, pack_msg = core.create_packing_list_report(final_df, packing_report_config)
    assert pack_success
    assert os.path.exists(packing_report_config["output_filename"])

    # Stock Export
    export_report_config = config["stock_exports"][0]
    export_report_config["output_filename"] = str(output_dir / export_report_config["output_filename"])
    export_success, export_msg = core.create_stock_export_report(
        final_df, export_report_config
    )
    assert export_success
    assert os.path.exists(export_report_config["output_filename"])


def test_normalize_unc_path():
    """Tests the UNC path normalization."""
    if os.name == "nt":
        assert core._normalize_unc_path("//server/share/file.txt") == "\\\\server\\share\\file.txt"
    else:
        assert core._normalize_unc_path("/server/share/file.txt") == "/server/share/file.txt"
    assert core._normalize_unc_path(None) is None


@pytest.mark.parametrize(
    "file_content,required_cols,delimiter,expected_result,expected_missing",
    [
        ("h1,h2,h3", ["h1", "h2"], ",", True, []),
        ("h1;h2;h3", ["h1", "h3"], ";", True, []),
        ("h1,h2,h3", ["h1", "h4"], ",", False, ["h4"]),
        ("h1,h2,h3", [], ",", True, []),
    ],
)
def test_validate_csv_headers(tmp_path, file_content, required_cols, delimiter, expected_result, expected_missing):
    """Tests the CSV header validation function with various inputs."""
    p = tmp_path / "test.csv"
    p.write_text(file_content)
    is_valid, missing = core.validate_csv_headers(str(p), required_cols, delimiter)
    assert is_valid == expected_result
    assert missing == expected_missing


def test_validate_csv_headers_file_not_found():
    """Tests header validation behavior when the input file does not exist."""
    is_valid, missing = core.validate_csv_headers("non_existent_file.csv", ["any"], ",")
    assert not is_valid
    assert "File not found" in missing[0]


def test_validate_csv_headers_generic_exception(mocker):
    """Tests header validation behavior when pandas raises an unexpected exception."""
    mocker.patch("pandas.read_csv", side_effect=Exception("Unexpected error"))
    is_valid, missing = core.validate_csv_headers("any_file.csv", ["any"], ",")
    assert not is_valid
    assert "An unexpected error occurred" in missing[0]


def test_run_full_analysis_file_not_found(mocker):
    """Tests run_full_analysis behavior when input files do not exist."""
    mocker.patch("os.path.exists", return_value=False)
    success, msg, _, _ = core.run_full_analysis("fake", "fake", "fake", ";", {})
    assert not success
    assert "input files were not found" in msg


def test_run_full_analysis_validation_fails(mocker):
    """Tests run_full_analysis behavior when DataFrame validation fails."""
    # This mocks the internal _validate_dataframes function to return errors
    mocker.patch("shopify_tool.core._validate_dataframes", return_value=["Missing column 'X'"])
    success, msg, _, _ = core.run_full_analysis(
        None, None, None, ";", {"test_stock_df": pd.DataFrame(), "test_orders_df": pd.DataFrame()}
    )
    assert not success
    assert "Missing column 'X'" in msg


def test_create_packing_list_report_exception(mocker):
    """Tests exception handling in the create_packing_list_report function."""
    mocker.patch("shopify_tool.packing_lists.create_packing_list", side_effect=Exception("Disk full"))
    analysis_df = pd.DataFrame()
    report_config = {"name": "FailList", "output_filename": "/tmp/fail.xlsx"}
    success, msg = core.create_packing_list_report(analysis_df, report_config)
    assert not success
    assert "Failed to create report" in msg


def test_create_stock_export_report_exception(mocker):
    """Tests exception handling in the create_stock_export_report function."""
    mocker.patch("shopify_tool.stock_export.create_stock_export", side_effect=Exception("Disk full"))
    analysis_df = pd.DataFrame()
    report_config = {"name": "FailExport", "output_filename": "/tmp/bad.xls"}
    success, msg = core.create_stock_export_report(analysis_df, report_config)
    assert not success
    assert "Failed to create stock export" in msg


def test_validate_dataframes_with_missing_columns():
    """Tests the internal _validate_dataframes helper function."""
    orders_df = pd.DataFrame({"Name": [1]})
    stock_df = pd.DataFrame({"Артикул": ["A"]})
    config = {
        "column_mappings": {"orders_required": ["Name", "Lineitem sku"], "stock_required": ["Артикул", "Наличност"]}
    }
    errors = core._validate_dataframes(orders_df, stock_df, config)
    assert len(errors) == 2
    assert "Missing required column in Orders file: 'Lineitem sku'" in errors
    assert "Missing required column in Stock file: 'Наличност'" in errors


def test_run_full_analysis_with_rules(mocker):
    """Tests that the rule engine is correctly called during a full analysis."""
    mock_engine_apply = mocker.patch("shopify_tool.rules.RuleEngine.apply")
    config = {
        "test_stock_df": make_stock_df(),
        "test_orders_df": make_orders_df(),
        "rules": [{"if": [], "then": []}],  # Presence of rules triggers the engine
    }
    core.run_full_analysis(None, None, None, ";", config)
    mock_engine_apply.assert_called_once()


def test_run_full_analysis_updates_history(tmp_path, mocker):
    """Tests that a successful analysis correctly updates the fulfillment history file."""
    # Setup files
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    stock_file = tmp_path / "stock.csv"
    stock_file.write_text("Артикул;Име;Наличност\nSKU-1;Item 1;10")
    orders_file = tmp_path / "orders.csv"
    orders_file.write_text(
        "Name,Lineitem sku,Lineitem quantity,Shipping Method,Shipping Country,Tags,Notes\n1001,SKU-1,1,dhl,BG,,\n"
    )
    history_file = tmp_path / "history.csv"
    history_file.write_text("Order_Number,Execution_Date\n999,2023-01-01")

    mocker.patch("shopify_tool.core.get_persistent_data_path", return_value=str(history_file))

    config = {
        "settings": {"stock_csv_delimiter": ";"},
        "column_mappings": {"orders_required": ["Name", "Lineitem sku"], "stock_required": ["Артикул", "Наличност"]},
        "rules": [],
    }

    # Run analysis
    core.run_full_analysis(str(stock_file), str(orders_file), str(output_dir), ";", config)

    # Check that history file was updated
    history_df = pd.read_csv(history_file)
    assert "1001" in history_df["Order_Number"].astype(str).values
    assert len(history_df) == 2


def test_create_packing_list_creates_dir(tmp_path):
    """Tests that the report generation function creates the output directory if needed."""
    output_dir = tmp_path / "non_existent_dir"
    output_file = output_dir / "report.xlsx"
    report_config = {"name": "Test", "output_filename": str(output_file)}
    core.create_packing_list_report(make_orders_df(), report_config)
    assert output_dir.exists()
