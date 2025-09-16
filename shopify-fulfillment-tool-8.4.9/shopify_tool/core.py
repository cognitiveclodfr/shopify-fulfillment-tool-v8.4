import os
import logging
import pandas as pd
from datetime import datetime
from . import analysis, packing_lists, stock_export
from .rules import RuleEngine
from .utils import get_persistent_data_path
import numpy as np

SYSTEM_TAGS = ["Repeat", "Priority", "Error"]

logger = logging.getLogger("ShopifyToolLogger")


def _normalize_unc_path(path):
    """Normalizes a path, which is especially useful for UNC paths on Windows."""
    if not path:
        return path
    # os.path.normpath will convert / to \ on Windows and handle other inconsistencies
    return os.path.normpath(path)


def _validate_dataframes(orders_df, stock_df, config):
    """Validates that the required columns are present in the dataframes.

    Checks the orders and stock DataFrames against the required columns
    specified in the application configuration.

    Args:
        orders_df (pd.DataFrame): The DataFrame containing order data.
        stock_df (pd.DataFrame): The DataFrame containing stock data.
        config (dict): The application configuration dictionary, which contains
            the 'column_mappings' with 'orders_required' and
            'stock_required' lists.

    Returns:
        list[str]: A list of error messages. If the list is empty,
                   validation passed.
    """
    errors = []
    column_mappings = config.get("column_mappings", {})
    required_orders_cols = column_mappings.get("orders_required", [])
    required_stock_cols = column_mappings.get("stock_required", [])

    for col in required_orders_cols:
        if col not in orders_df.columns:
            errors.append(f"Missing required column in Orders file: '{col}'")

    for col in required_stock_cols:
        if col not in stock_df.columns:
            errors.append(f"Missing required column in Stock file: '{col}'")

    return errors


def validate_csv_headers(file_path, required_columns, delimiter=","):
    """Quickly validates if a CSV file contains the required column headers.

    This function reads only the header row of a CSV file to check for the
    presence of required columns without loading the entire file into memory.

    Args:
        file_path (str): The path to the CSV file.
        required_columns (list[str]): A list of column names that must be present.
        delimiter (str, optional): The delimiter used in the CSV file.
            Defaults to ",".

    Returns:
        tuple[bool, list[str]]: A tuple containing:
            - bool: True if all required columns are present, False otherwise.
            - list[str]: A list of missing columns. An empty list if all are
              present. Returns a list with an error message on file read
              errors.
    """
    if not required_columns:
        return True, []

    try:
        headers = pd.read_csv(file_path, nrows=0, delimiter=delimiter).columns.tolist()
        missing_columns = [col for col in required_columns if col not in headers]

        if not missing_columns:
            return True, []
        else:
            return False, missing_columns

    except FileNotFoundError:
        return False, [f"File not found at path: {file_path}"]
    except pd.errors.ParserError as e:
        logger.error(f"Parser error validating CSV '{file_path}': {e}", exc_info=True)
        return False, [f"Could not parse file. It might be corrupt or not a valid CSV. Error: {e}"]
    except Exception as e:
        logger.error(f"Unexpected error validating CSV headers for {file_path}: {e}", exc_info=True)
        return False, [f"An unexpected error occurred: {e}"]


def run_full_analysis(stock_file_path, orders_file_path, output_dir_path, stock_delimiter, config):
    """Orchestrates the entire fulfillment analysis process.

    This function serves as the main entry point for the core analysis logic.
    It performs the following steps:
    1. Loads stock and order data from CSV files.
    2. Validates that the data contains the required columns.
    3. Loads historical fulfillment data.
    4. Runs the fulfillment simulation to determine order statuses.
    5. Applies stock alerts and custom tagging rules.
    6. Saves a detailed analysis report to an Excel file, including summaries.
    7. Updates the fulfillment history with newly fulfilled orders.

    Args:
        stock_file_path (str | None): Path to the stock data CSV file. Can be
            None for testing purposes if a DataFrame is provided in `config`.
        orders_file_path (str | None): Path to the Shopify orders export CSV
            file. Can be None for testing.
        output_dir_path (str): Path to the directory where the output report
            will be saved.
        stock_delimiter (str): The delimiter used in the stock CSV file.
        config (dict): The application configuration dictionary. It can also
            contain test DataFrames under 'test_stock_df' and
            'test_orders_df' keys.

    Returns:
        tuple[bool, str | None, pd.DataFrame | None, dict | None]:
            A tuple containing:
            - bool: True for success, False for failure.
            - str | None: A message indicating the result. On success, this
              is the path to the output file. On failure, it's an error
              message.
            - pd.DataFrame | None: The final analysis DataFrame if successful,
              otherwise None.
            - dict | None: A dictionary of calculated statistics if
              successful, otherwise None.
    """
    logger.info("--- Starting Full Analysis Process ---")
    # 1. Load data
    logger.info("Step 1: Loading data files...")
    if stock_file_path is not None and orders_file_path is not None:
        # Normalize paths to handle UNC paths from network shares correctly
        stock_file_path = _normalize_unc_path(stock_file_path)
        orders_file_path = _normalize_unc_path(orders_file_path)

        if not os.path.exists(stock_file_path) or not os.path.exists(orders_file_path):
            return False, "One or both input files were not found.", None, None

        logger.info(f"Reading stock file from normalized path: {stock_file_path}")
        stock_df = pd.read_csv(stock_file_path, delimiter=stock_delimiter)
        logger.info(f"Reading orders file from normalized path: {orders_file_path}")
        orders_df = pd.read_csv(orders_file_path)
    else:
        # For testing: allow passing DataFrames directly
        stock_df = config.get("test_stock_df")
        orders_df = config.get("test_orders_df")
        history_df = config.get("test_history_df", pd.DataFrame({"Order_Number": []}))
    logger.info("Data loaded successfully.")

    # Validate dataframes
    validation_errors = _validate_dataframes(orders_df, stock_df, config)
    if validation_errors:
        error_message = "\n".join(validation_errors)
        logger.error(f"Validation Error: {error_message}")
        return False, error_message, None, None

    # Use a persistent path for the history file to avoid permission errors on network drives
    history_path = get_persistent_data_path("fulfillment_history.csv")
    if stock_file_path is not None and orders_file_path is not None:
        try:
            history_df = pd.read_csv(history_path)
            logger.info(f"Loaded {len(history_df)} records from fulfillment history.")
        except FileNotFoundError:
            history_df = pd.DataFrame(columns=["Order_Number", "Execution_Date"])
            logger.warning("Fulfillment history not found. A new one will be created.")

    # 2. Run analysis (computation only)
    logger.info("Step 2: Running fulfillment simulation...")
    final_df, summary_present_df, summary_missing_df, stats = analysis.run_analysis(stock_df, orders_df, history_df)
    logger.info("Analysis computation complete.")

    # 2.5. Add stock alerts based on config
    low_stock_threshold = config.get("settings", {}).get("low_stock_threshold")
    if low_stock_threshold is not None and "Final_Stock" in final_df.columns:
        logger.info(f"Applying low stock threshold: < {low_stock_threshold}")
        final_df["Stock_Alert"] = np.where(final_df["Final_Stock"] < low_stock_threshold, "Low Stock", "")

    # 2.6. Apply the new rule engine
    rules = config.get("rules", [])
    if rules:
        logger.info("Applying new rule engine...")
        engine = RuleEngine(rules)
        final_df = engine.apply(final_df)
        logger.info("Rule engine application complete.")

    # 3. Save Excel report (skip in test mode)
    if stock_file_path is not None and orders_file_path is not None:
        logger.info("Step 3: Saving analysis report to Excel...")
        if not os.path.exists(output_dir_path):
            os.makedirs(output_dir_path)
        output_file_path = os.path.join(output_dir_path, "fulfillment_analysis.xlsx")

        with pd.ExcelWriter(output_file_path, engine="xlsxwriter") as writer:
            final_df.to_excel(writer, sheet_name="fulfillment_analysis", index=False)
            summary_present_df.to_excel(writer, sheet_name="Summary_Present", index=False)
            summary_missing_df.to_excel(writer, sheet_name="Summary_Missing", index=False)

            workbook = writer.book
            report_info_sheet = workbook.add_worksheet("Report Info")
            generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report_info_sheet.write("A1", "Report Generated On:")
            report_info_sheet.write("B1", generation_time)
            report_info_sheet.set_column("A:B", 25)

            worksheet = writer.sheets["fulfillment_analysis"]
            highlight_format = workbook.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006"})
            for idx, col in enumerate(final_df):
                max_len = max((final_df[col].astype(str).map(len).max(), len(str(col)))) + 2
                worksheet.set_column(idx, idx, max_len)
            for row_num, status in enumerate(final_df["Order_Fulfillment_Status"]):
                if status == "Not Fulfillable":
                    worksheet.set_row(row_num + 1, None, highlight_format)
        logger.info(f"Excel report saved to '{output_file_path}'")

        # 4. Update history
        logger.info("Step 4: Updating fulfillment history...")
        newly_fulfilled = final_df[final_df["Order_Fulfillment_Status"] == "Fulfillable"][
            ["Order_Number"]
        ].drop_duplicates()
        if not newly_fulfilled.empty:
            newly_fulfilled["Execution_Date"] = datetime.now().strftime("%Y-%m-%d")
            updated_history = pd.concat([history_df, newly_fulfilled]).drop_duplicates(
                subset=["Order_Number"], keep="last"
            )
            updated_history.to_csv(history_path, index=False)
            logger.info(f"Updated fulfillment history with {len(newly_fulfilled)} new records.")
        return True, output_file_path, final_df, stats
    else:
        # For tests, just return the DataFrames
        return True, None, final_df, stats


def create_packing_list_report(analysis_df, report_config):
    """Generates a single packing list report based on a report configuration.

    Uses the provided analysis DataFrame and a specific report configuration
    to filter and format a packing list. The resulting report is saved to the
    location specified in the configuration.

    Args:
        analysis_df (pd.DataFrame): The main analysis DataFrame containing
            fulfillment data.
        report_config (dict): A dictionary from the main config file that
            defines the filters, output filename, excluded SKUs, and other
            settings for this specific report.

    Returns:
        tuple[bool, str]: A tuple containing:
            - bool: True for success, False for failure.
            - str: A message indicating the result (e.g., success message with
              file path or an error description).
    """
    report_name = report_config.get("name", "Unknown Report")
    try:
        output_file = report_config["output_filename"]
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        packing_lists.create_packing_list(
            analysis_df=analysis_df,
            output_file=output_file,
            report_name=report_name,
            filters=report_config.get("filters"),
            exclude_skus=report_config.get("exclude_skus"),  # Pass the new parameter
        )
        success_message = f"Report '{report_name}' created successfully at '{output_file}'."
        return True, success_message
    except KeyError as e:
        error_message = f"Configuration error for report '{report_name}': Missing key {e}."
        logger.error(f"Config error for packing list '{report_name}': {e}", exc_info=True)
        return False, error_message
    except PermissionError:
        output_filename = report_config.get('output_filename', 'N/A')
        error_message = f"Permission denied. Could not write report to '{output_filename}'."
        logger.error(
            f"Permission error creating packing list '{report_name}' at '{output_filename}'", exc_info=True
        )
        return False, error_message
    except Exception as e:
        error_message = f"Failed to create report '{report_name}'. See logs/app_errors.log for details."
        logger.error(f"Error creating packing list '{report_name}': {e}", exc_info=True)
        return False, error_message


def get_unique_column_values(df, column_name):
    """Extracts unique, sorted, non-null values from a DataFrame column.

    Args:
        df (pd.DataFrame): The DataFrame to extract values from.
        column_name (str): The name of the column to get unique values from.

    Returns:
        list[str]: A sorted list of unique string-converted values, or an
                   empty list if the column doesn't exist or an error occurs.
    """
    if df.empty or column_name not in df.columns:
        return []
    try:
        unique_values = df[column_name].dropna().unique().tolist()
        return sorted([str(v) for v in unique_values])
    except Exception:
        return []


def create_stock_export_report(analysis_df, report_config):
    """Generates a single stock export report based on a configuration.

    Args:
        analysis_df (pd.DataFrame): The main analysis DataFrame.
        report_config (dict): The configuration for the specific stock export.

    Returns:
        tuple[bool, str]: A tuple containing a success flag and a status message.
    """
    report_name = report_config.get("name", "Untitled Stock Export")
    try:
        output_filename = report_config["output_filename"]
        filters = report_config.get("filters")

        # Ensure the output directory exists
        output_dir = os.path.dirname(output_filename)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        stock_export.create_stock_export(
            analysis_df,
            output_filename,
            report_name=report_name,
            filters=filters,
        )
        success_message = f"Stock export '{report_name}' created successfully at '{output_filename}'."
        return True, success_message
    except KeyError as e:
        error_message = f"Configuration error for stock export '{report_name}': Missing key {e}."
        logger.error(f"Config error for stock export '{report_name}': {e}", exc_info=True)
        return False, error_message
    except PermissionError:
        error_message = "Permission denied. Could not write stock export."
        logger.error(f"Permission error creating stock export '{report_name}'", exc_info=True)
        return False, error_message
    except Exception as e:
        error_message = f"Failed to create stock export '{report_name}'. See logs for details."
        logger.error(f"Error creating stock export '{report_name}': {e}", exc_info=True)
        return False, error_message
