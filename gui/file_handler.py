import os
import logging
from PySide6.QtWidgets import QFileDialog

from shopify_tool import core


class FileHandler:
    """Handles file selection dialogs, validation, and loading logic.

    This class encapsulates the functionality related to file I/O initiated
    by the user, such as selecting orders and stock files. It interacts with
    the `QFileDialog` to get file paths and then triggers validation on those
    files.

    Attributes:
        mw (MainWindow): A reference to the main window instance.
        log (logging.Logger): A logger for this class.
    """

    def __init__(self, main_window):
        """Initializes the FileHandler.

        Args:
            main_window (MainWindow): The main window instance that this
                handler will manage file operations for.
        """
        self.mw = main_window
        self.log = logging.getLogger(__name__)

    def select_orders_file(self):
        """Opens a file dialog for the user to select the orders CSV file.

        After a file is selected, it updates the corresponding UI labels,
        triggers header validation for the file, and checks if the application
        is ready to run the analysis.
        """
        filepath, _ = QFileDialog.getOpenFileName(self.mw, "Select Orders File", "", "CSV files (*.csv)")
        if filepath:
            self.mw.orders_file_path = filepath
            self.mw.orders_file_path_label.setText(os.path.basename(filepath))
            self.log.info(f"Orders file selected: {filepath}")
            self.validate_file("orders")
            self.check_files_ready()

    def select_stock_file(self):
        """Opens a file dialog for the user to select the stock CSV file.

        After a file is selected, it updates the corresponding UI labels,
        triggers header validation for the file, and checks if the application
        is ready to run the analysis.
        """
        filepath, _ = QFileDialog.getOpenFileName(self.mw, "Select Stock File", "", "CSV files (*.csv)")
        if filepath:
            self.mw.stock_file_path = filepath
            self.mw.stock_file_path_label.setText(os.path.basename(filepath))
            self.log.info(f"Stock file selected: {filepath}")
            self.validate_file("stock")
            self.check_files_ready()

    def validate_file(self, file_type):
        """Validates that a selected CSV file contains the required headers.

        It reads the required column names from the application configuration
        and uses `core.validate_csv_headers` to perform the check. The result
        is displayed to the user via a status label (✓ or ✗) with a tooltip
        providing details on failure.

        Args:
            file_type (str): The type of file to validate, either "orders" or
                             "stock".
        """
        if file_type == "orders":
            path = self.mw.orders_file_path
            label = self.mw.orders_file_status_label
            required_cols = self.mw.config.get("column_mappings", {}).get("orders_required", [])
            delimiter = ","
        else:  # stock
            path = self.mw.stock_file_path
            label = self.mw.stock_file_status_label
            required_cols = self.mw.config.get("column_mappings", {}).get("stock_required", [])
            delimiter = self.mw.config.get("settings", {}).get("stock_csv_delimiter", ";")

        if not path:
            self.log.warning(f"Validation skipped for '{file_type}': path is missing.")
            return

        self.log.info(f"Validating '{file_type}' file: {path}")
        is_valid, missing_cols = core.validate_csv_headers(path, required_cols, delimiter)

        if is_valid:
            label.setText("✓")
            label.setStyleSheet("color: green; font-weight: bold;")
            label.setToolTip("File is valid.")
            self.log.info(f"'{file_type}' file is valid.")
        else:
            label.setText("✗")
            label.setStyleSheet("color: red; font-weight: bold;")
            tooltip_text = f"Missing columns: {', '.join(missing_cols)}"
            label.setToolTip(tooltip_text)
            self.log.warning(f"'{file_type}' file is invalid. {tooltip_text}")

    def check_files_ready(self):
        """Checks if both orders and stock files are selected and valid.

        If both files have been selected and have passed validation, this
        method enables the main 'Run Analysis' button in the UI. Otherwise,
        the button remains disabled.
        """
        orders_ok = self.mw.orders_file_path and self.mw.orders_file_status_label.text() == "✓"
        stock_ok = self.mw.stock_file_path and self.mw.stock_file_status_label.text() == "✓"
        if orders_ok and stock_ok:
            self.mw.run_analysis_button.setEnabled(True)
            self.log.info("Both files are validated and ready for analysis.")
        else:
            self.mw.run_analysis_button.setEnabled(False)
