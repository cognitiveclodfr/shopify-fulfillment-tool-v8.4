import logging
import pandas as pd

logger = logging.getLogger("ShopifyToolLogger")


def create_stock_export(analysis_df, output_file, report_name="Stock Export", filters=None):
    """Creates a stock export .xls file from scratch.

    This function generates a stock export file programmatically using pandas,
    eliminating the need for a physical template file. The structure is
    hard-coded to ensure consistency.

    Key steps in the process:
    1.  **Filtering**: It filters the main analysis DataFrame to include only
        'Fulfillable' orders that match the provided filter criteria.
    2.  **Summarization**: It summarizes the filtered data, calculating the total
        quantity for each unique SKU.
    3.  **DataFrame Creation**: It creates a new DataFrame with the required
        columns: 'Артикул' (for SKU) and 'Наличност' (for quantity).
    4.  **Saving**: The new DataFrame is saved to the specified .xls output file.

    Args:
        analysis_df (pd.DataFrame): The main DataFrame from the fulfillment
            analysis.
        output_file (str): The full path where the new .xls file will be saved.
        report_name (str, optional): The name of the report, used for logging.
            Defaults to "Stock Export".
        filters (list[dict], optional): A list of dictionaries defining filter
            conditions to apply before summarizing the data. Defaults to None.
    """
    try:
        logger.info(f"--- Creating report: '{report_name}' ---")

        # Build the query string to filter the DataFrame
        query_parts = ["Order_Fulfillment_Status == 'Fulfillable'"]
        if filters:
            for f in filters:
                field = f.get("field")
                operator = f.get("operator")
                value = f.get("value")

                if not all([field, operator, value is not None]):
                    logger.warning(f"Skipping invalid filter: {f}")
                    continue

                # Correctly quote string values for the query
                if isinstance(value, str):
                    formatted_value = repr(value)
                else:
                    # For lists (for 'in'/'not in') and numbers, no extra quotes are needed.
                    formatted_value = value

                query_parts.append(f"`{field}` {operator} {formatted_value}")

        full_query = " & ".join(query_parts)
        filtered_items = analysis_df.query(full_query).copy()

        if filtered_items.empty:
            logger.warning(f"Report '{report_name}': No items found matching the criteria.")
            # Still create an empty file with headers
            export_df = pd.DataFrame(columns=["Артикул", "Наличност"])
        else:
            # Summarize quantities by SKU
            sku_summary = filtered_items.groupby("SKU")["Quantity"].sum().astype(int).reset_index()
            sku_summary = sku_summary[sku_summary["Quantity"] > 0]

            if sku_summary.empty:
                logger.warning(f"Report '{report_name}': No items with a positive quantity to export.")
                export_df = pd.DataFrame(columns=["Артикул", "Наличност"])
            else:
                logger.info(f"Found {len(sku_summary)} unique SKUs to write for report '{report_name}'.")
                # Create the final DataFrame in the required format
                export_df = pd.DataFrame(
                    {
                        "Артикул": sku_summary["SKU"],
                        "Наличност": sku_summary["Quantity"],
                    }
                )

        # Save to an .xls file
        try:
            with pd.ExcelWriter(output_file, engine="xlwt") as writer:
                export_df.to_excel(writer, index=False, sheet_name="Sheet1")
            logger.info(f"Stock export '{report_name}' created successfully at '{output_file}'.")
        except Exception as e:
            # Fallback for environments where xlwt might not be properly registered
            if "No Excel writer 'xlwt'" in str(e):
                logger.warning("Pandas failed to find 'xlwt' engine. Trying direct save with xlwt.")
                import xlwt
                workbook = xlwt.Workbook()
                sheet = workbook.add_sheet('Sheet1')

                # Write header
                for col_num, value in enumerate(export_df.columns):
                    sheet.write(0, col_num, value)

                # Write data
                for row_num, row in export_df.iterrows():
                    for col_num, value in enumerate(row):
                        sheet.write(row_num + 1, col_num, value)

                workbook.save(output_file)
                logger.info(
                    f"Stock export '{report_name}' created successfully at '{output_file}' using direct xlwt save."
                )
            else:
                raise e

    except Exception as e:
        logger.error(f"Error while creating stock export '{report_name}': {e}")
