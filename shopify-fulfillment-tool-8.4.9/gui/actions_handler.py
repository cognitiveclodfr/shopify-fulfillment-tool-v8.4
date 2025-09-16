import os
import logging
from datetime import datetime
import pandas as pd

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox, QInputDialog

from gui.worker import Worker
from shopify_tool import core
from shopify_tool.analysis import toggle_order_fulfillment
from gui.settings_window_pyside import SettingsWindow
from gui.report_selection_dialog import ReportSelectionDialog
from gui.report_builder_window_pyside import ReportBuilderWindow


class ActionsHandler(QObject):
    """Handles application logic triggered by user actions from the UI.

    This class acts as an intermediary between the `MainWindow` (UI) and the
    backend `shopify_tool` modules. It contains slots that are connected to
    UI widget signals (e.g., button clicks). When a signal is received, the
    handler executes the corresponding application logic, such as running an
    analysis, generating a report, or modifying data.

    It uses a `QThreadPool` to run long-running tasks (like analysis and
    report generation) in the background to keep the UI responsive.

    Signals:
        data_changed: Emitted whenever the main analysis DataFrame is modified,
                      signaling the UI to refresh its views.

    Attributes:
        mw (MainWindow): A reference to the main window instance.
        log (logging.Logger): A logger for this class.
    """

    data_changed = Signal()

    def __init__(self, main_window):
        """Initializes the ActionsHandler.

        Args:
            main_window (MainWindow): The main window instance that this
                handler will manage actions for.
        """
        super().__init__()
        self.mw = main_window
        self.log = logging.getLogger(__name__)

    def create_new_session(self):
        """Creates a new, unique, date-stamped session folder for output files.

        This folder is used as the destination for all reports generated
        during the current work session. Upon successful creation, it enables
        the file loading buttons in the UI.
        """
        try:
            base_output_dir = self.mw.active_profile_config["paths"].get("output_dir_stock", "data/output")
            os.makedirs(base_output_dir, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d")
            session_id = 1
            while True:
                session_path = os.path.join(base_output_dir, f"{date_str}_session_{session_id}")
                if not os.path.exists(session_path):
                    break
                session_id += 1
            os.makedirs(session_path, exist_ok=True)
            self.mw.session_path = session_path
            self.mw.session_path_label.setText(f"Current Session: {os.path.basename(self.mw.session_path)}")
            self.mw.load_orders_btn.setEnabled(True)
            self.mw.load_stock_btn.setEnabled(True)
            self.mw.log_activity("Session", f"New session started. Output: {self.mw.session_path}")
        except Exception as e:
            self.log.error(f"Failed to create new session: {e}", exc_info=True)
            QMessageBox.critical(self.mw, "Session Error", f"Could not create a new session folder.\nError: {e}")

    def run_analysis(self):
        """Triggers the main fulfillment analysis in a background thread.

        It creates a `Worker` to run the `core.run_full_analysis` function,
        preventing the UI from freezing. It connects the worker's signals
        to the appropriate slots for handling completion or errors.
        """
        if not self.mw.session_path:
            QMessageBox.critical(self.mw, "Session Error", "Please create a new session before running an analysis.")
            return
        self.mw.ui_manager.set_ui_busy(True)
        self.log.info("Starting analysis thread.")
        stock_delimiter = self.mw.active_profile_config["settings"]["stock_csv_delimiter"]
        worker = Worker(
            core.run_full_analysis,
            self.mw.stock_file_path,
            self.mw.orders_file_path,
            self.mw.session_path,
            stock_delimiter,
            self.mw.active_profile_config,
        )
        worker.signals.result.connect(self.on_analysis_complete)
        worker.signals.error.connect(self.on_task_error)
        worker.signals.finished.connect(lambda: self.mw.ui_manager.set_ui_busy(False))
        self.mw.threadpool.start(worker)

    def on_analysis_complete(self, result):
        """Handles the 'result' signal from the analysis worker thread.

        If the analysis was successful, it updates the main DataFrame,
        emits the `data_changed` signal to refresh the UI, and logs the
        activity. If it failed, it displays a critical error message.

        Args:
            result (tuple): The tuple returned by `core.run_full_analysis`.
        """
        self.log.info("Analysis thread finished.")
        success, result_msg, df, stats = result
        if success:
            self.mw.analysis_results_df = df
            self.mw.analysis_stats = stats
            self.data_changed.emit()
            self.mw.log_activity("Analysis", f"Analysis complete. Report saved to: {result_msg}")
        else:
            self.log.error(f"Analysis failed: {result_msg}")
            QMessageBox.critical(self.mw, "Analysis Error", f"An error occurred during analysis:\n{result_msg}")

    def on_task_error(self, error):
        """Handles the 'error' signal from any worker thread.

        Logs the exception and displays a critical error message to the user.

        Args:
            error (tuple): A tuple containing the exception type, value, and
                traceback.
        """
        exctype, value, tb = error
        self.log.error(f"An unexpected error occurred in a background task: {value}\n{tb}", exc_info=True)
        msg = f"An unexpected error occurred in a background task:\n{value}\n\nTraceback:\n{tb}"
        QMessageBox.critical(self.mw, "Task Exception", msg)

    def open_settings_window(self):
        """Opens the settings dialog window for the active profile.

        If the settings are saved in the dialog, it updates the active profile's
        configuration in the main config object and saves it to file.
        """
        dialog = SettingsWindow(self.mw, self.mw.active_profile_config, self.mw.analysis_results_df)
        if dialog.exec():
            # Update the active profile's config with the data from the dialog
            self.mw.config["profiles"][self.mw.active_profile_name] = dialog.config_data
            self.mw._save_config()  # Use the centralized save method

            # Refresh the active config in the main window
            self.mw.active_profile_config = dialog.config_data

            self.mw.log_activity("Settings", f"Settings for profile '{self.mw.active_profile_name}' saved.")
            self.log.info(f"Settings for profile '{self.mw.active_profile_name}' saved.")

    def open_report_selection_dialog(self, report_type):
        """Opens a dialog to select and generate a pre-configured report.

        Args:
            report_type (str): The key for the report configuration list in
                the main config (e.g., "packing_lists", "stock_exports").
        """
        reports_config = self.mw.active_profile_config.get(report_type, [])
        if not reports_config:
            msg = (f"No {report_type.replace('_', ' ')} configured in the active "
                   f"profile ('{self.mw.active_profile_name}').")
            QMessageBox.information(self.mw, "No Reports", msg)
            return
        dialog = ReportSelectionDialog(report_type, reports_config, self.mw)
        dialog.reportSelected.connect(lambda rc: self.run_report_logic(report_type, rc))
        dialog.exec()

    def run_report_logic(self, report_type, report_config):
        """Triggers the report generation in a background thread.

        Based on the `report_type`, it creates a `Worker` to run the
        appropriate report generation function from the `core` module.

        Args:
            report_type (str): The type of report to generate.
            report_config (dict): The specific configuration for the selected
                report.
        """
        if not self.mw.session_path:
            QMessageBox.critical(self.mw, "Session Error", "Please create a new session before generating reports.")
            return
        self.mw.log_activity("Report", f"Generating report: {report_config.get('name')}")
        self.log.info(f"Starting report generation for '{report_config.get('name')}'")
        if report_type == "packing_lists":
            relative_path = report_config.get("output_filename", "default_packing_list.xlsx")
            output_file = os.path.join(self.mw.session_path, os.path.basename(relative_path))
            report_config_copy = report_config.copy()
            report_config_copy["output_filename"] = output_file
            worker = Worker(
                core.create_packing_list_report,
                analysis_df=self.mw.analysis_results_df,
                report_config=report_config_copy,
            )
        elif report_type == "stock_exports":
            base_filename = report_config.get("output_filename", "default_stock_export.xls")
            datestamp = datetime.now().strftime("%Y-%m-%d")
            name, ext = os.path.splitext(base_filename)
            timestamped_filename = f"{name}_{datestamp}{ext}"
            output_file = os.path.join(self.mw.session_path, os.path.basename(timestamped_filename))
            report_config_copy = report_config.copy()
            report_config_copy["output_filename"] = output_file
            worker = Worker(
                core.create_stock_export_report,
                analysis_df=self.mw.analysis_results_df,
                report_config=report_config_copy,
            )
        else:
            QMessageBox.critical(self.mw, "Error", "Unknown report type.")
            return
        worker.signals.result.connect(self.on_report_generation_complete)
        worker.signals.error.connect(self.on_task_error)
        self.mw.threadpool.start(worker)

    def on_report_generation_complete(self, result):
        """Handles the 'result' signal from a report generation worker.

        Logs the outcome and shows a message to the user on success or failure.

        Args:
            result (tuple): The tuple returned by the report generation function.
        """
        success, message = result
        if success:
            self.mw.log_activity("Report Generation", message)
            self.log.info(f"Report generated successfully: {message}")
        else:
            self.log.error(f"Report generation failed: {message}")
            QMessageBox.critical(self.mw, "Error", message)

    def toggle_fulfillment_status_for_order(self, order_number):
        """Toggles the fulfillment status of all items in a given order.

        Calls the `analysis.toggle_order_fulfillment` function and updates
        the UI if the change is successful.

        Args:
            order_number (str): The order number to modify.
        """
        success, result, updated_df = toggle_order_fulfillment(self.mw.analysis_results_df, order_number)
        if success:
            self.mw.analysis_results_df = updated_df
            self.data_changed.emit()
            new_status = updated_df.loc[updated_df["Order_Number"] == order_number, "Order_Fulfillment_Status"].iloc[0]
            self.mw.log_activity("Manual Edit", f"Order {order_number} status changed to '{new_status}'.")
            self.log.info(f"Order {order_number} status changed to '{new_status}'.")
        else:
            self.log.warning(f"Failed to toggle status for order {order_number}: {result}")
            QMessageBox.critical(self.mw, "Error", result)

    def open_report_builder_window(self):
        """Opens the custom report builder dialog window."""
        if self.mw.analysis_results_df.empty:
            QMessageBox.warning(self.mw, "No Data", "Please run an analysis before using the Report Builder.")
            return
        dialog = ReportBuilderWindow(self.mw.analysis_results_df, self.mw)
        dialog.exec()

    def add_tag_manually(self, order_number):
        """Opens a dialog to add a manual tag to an order's 'Status_Note'.

        Args:
            order_number (str): The order number to add the tag to.
        """
        tag_to_add, ok = QInputDialog.getText(self.mw, "Add Manual Tag", "Enter tag to add:")
        if ok and tag_to_add:
            order_rows_indices = self.mw.analysis_results_df[
                self.mw.analysis_results_df["Order_Number"] == order_number
            ].index
            if "Status_Note" not in self.mw.analysis_results_df.columns:
                self.mw.analysis_results_df["Status_Note"] = ""
            for index in order_rows_indices:
                current_notes = self.mw.analysis_results_df.loc[index, "Status_Note"]
                if pd.isna(current_notes) or current_notes == "":
                    new_notes = tag_to_add
                elif tag_to_add not in current_notes.split(","):
                    new_notes = f"{current_notes}, {tag_to_add}"
                else:
                    new_notes = current_notes
                self.mw.analysis_results_df.loc[index, "Status_Note"] = new_notes
            self.data_changed.emit()
            self.mw.log_activity("Manual Tag", f"Added note '{tag_to_add}' to order {order_number}.")

    def remove_item_from_order(self, row_index):
        """Removes a single item (a row) from the analysis DataFrame.

        Args:
            row_index (int): The integer index of the row to remove.
        """
        order_number = self.mw.analysis_results_df.iloc[row_index]["Order_Number"]
        sku = self.mw.analysis_results_df.iloc[row_index]["SKU"]
        reply = QMessageBox.question(
            self.mw,
            "Confirm Delete",
            f"Are you sure you want to remove item {sku} from order {order_number}?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.mw.analysis_results_df.drop(self.mw.analysis_results_df.index[row_index], inplace=True)
            self.mw.analysis_results_df.reset_index(drop=True, inplace=True)
            self.data_changed.emit()
            self.mw.log_activity("Data Edit", f"Removed item {sku} from order {order_number}.")

    def remove_entire_order(self, order_number):
        """Removes all rows associated with a given order number.

        Args:
            order_number (str): The order number to remove completely.
        """
        reply = QMessageBox.question(
            self.mw,
            "Confirm Delete",
            f"Are you sure you want to remove the entire order {order_number}?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.mw.analysis_results_df = self.mw.analysis_results_df[
                self.mw.analysis_results_df["Order_Number"] != order_number
            ].reset_index(drop=True)
            self.data_changed.emit()
            self.mw.log_activity("Data Edit", f"Removed order {order_number}.")
