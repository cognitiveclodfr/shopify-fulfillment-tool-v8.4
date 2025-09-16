from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton
from PySide6.QtCore import Signal, Slot


class ReportSelectionDialog(QDialog):
    """A dialog that dynamically creates buttons for selecting a pre-configured report.

    This dialog is populated with a button for each report found in the
    application's configuration file for a given report type (e.g.,
    'packing_lists' or 'stock_exports'). When the user clicks a button, the
    dialog emits a signal containing the configuration for that specific
    report and then closes.

    Signals:
        reportSelected (dict): Emitted when a report button is clicked,
                               carrying the configuration dictionary for that
                               report.
    """

    # Signal that emits the selected report configuration when a button is clicked
    reportSelected = Signal(dict)

    def __init__(self, report_type, reports_config, parent=None):
        """Initializes the ReportSelectionDialog.

        Args:
            report_type (str): The type of reports to display (e.g.,
                "packing_lists"). Used for the window title.
            reports_config (list[dict]): A list of report configuration
                dictionaries, each used to create a button.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)

        self.setWindowTitle(f"Select {report_type.replace('_', ' ').title()}")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        if not reports_config:
            # You can add a QLabel here to show a message
            pass
        else:
            for report_config in reports_config:
                button = QPushButton(report_config.get("name", "Unknown Report"))
                # Use a lambda to capture the specific config for this button
                button.clicked.connect(lambda checked=False, rc=report_config: self.on_report_button_clicked(rc))
                layout.addWidget(button)

    @Slot(dict)
    def on_report_button_clicked(self, report_config):
        """Handles the click of any report button.

        Emits the `reportSelected` signal with the configuration of the
        clicked report and then closes the dialog.

        Args:
            report_config (dict): The configuration dictionary associated
                with the button that was clicked.
        """
        self.reportSelected.emit(report_config)
        self.accept()
