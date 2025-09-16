import sys
import json
import pandas as pd
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QTabWidget,
    QWidget,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QComboBox,
)
from PySide6.QtCore import Qt

from shopify_tool.core import get_unique_column_values


class SettingsWindow(QDialog):
    """A dialog window for viewing and editing all application settings.

    This window provides a tabbed interface for modifying different sections
    of the application's configuration, including:
    - General settings and paths.
    - The rule engine's rule definitions.
    - Pre-configured packing list reports.
    - Pre-configured stock export reports.

    The UI is built dynamically based on the current configuration data that
    is passed in during initialization. It allows for adding, editing, and
    deleting rules, reports, and their constituent parts.

    Attributes:
        config_data (dict): A deep copy of the application's configuration.
        analysis_df (pd.DataFrame): The main analysis DataFrame, used to
            populate dynamic dropdowns for filter values.
        rule_widgets (list): A list of dictionaries, each holding references
            to the UI widgets for a single rule.
        packing_list_widgets (list): References to packing list UI widgets.
        stock_export_widgets (list): References to stock export UI widgets.
    """

    # Constants for builders
    FILTER_OPERATORS = ["==", "!=", "in", "not in", "contains"]
    ACTION_TYPES = ["ADD_TAG", "SET_STATUS", "SET_PRIORITY", "EXCLUDE_FROM_REPORT", "EXCLUDE_SKU"]

    # Operators grouped by the data type they apply to
    OPERATORS_BY_TYPE = {
        "text": [
            "equals", "does not equal", "contains", "does not contain",
            "starts with", "ends with",
        ],
        "numeric": [
            "equals", "does not equal", "is greater than", "is less than",
        ],
        "general": [ # Apply to all types
            "is empty", "is not empty"
        ]
    }

    def __init__(self, parent, config, analysis_df=None):
        """Initializes the SettingsWindow.

        Args:
            parent (QWidget): The parent widget.
            config (dict): The application configuration dictionary. A deep
                copy is made to avoid modifying the original until saved.
            analysis_df (pd.DataFrame, optional): The current analysis
                DataFrame, used for populating filter value dropdowns.
                Defaults to None.
        """
        super().__init__(parent)
        self.parent = parent
        self.config_data = json.loads(json.dumps(config))
        self.analysis_df = analysis_df if analysis_df is not None else pd.DataFrame()

        # Ensure mappings sections exist with the correct structure
        if not isinstance(self.config_data.get("column_mappings"), dict) or not all(
            k in self.config_data["column_mappings"] for k in ["orders", "stock"]
        ):
            self.config_data["column_mappings"] = {
                "orders": {
                    "name": "Name",
                    "sku": "Lineitem sku",
                    "quantity": "Lineitem quantity",
                    "shipping_provider": "Shipping Provider",
                },
                "stock": {"sku": "Артикул", "stock": "Наличност"},
            }
        if "courier_mappings" not in self.config_data:
            self.config_data["courier_mappings"] = {}

        self.rule_widgets = []
        self.packing_list_widgets = []
        self.stock_export_widgets = []
        self.column_mapping_widgets = {}
        self.courier_mapping_widgets = []

        # Determine available columns and their types for dynamic dropdowns
        self.filterable_columns = []
        self.numeric_columns = []
        if not self.analysis_df.empty:
            self.filterable_columns = sorted(self.analysis_df.columns.tolist())
            self.numeric_columns = self.analysis_df.select_dtypes(include='number').columns.tolist()

        self.setWindowTitle("Application Settings")
        self.setMinimumSize(800, 700)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self.create_general_tab()
        self.create_rules_tab()
        self.create_packing_lists_tab()
        self.create_stock_exports_tab()
        self.create_mappings_tab()

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    # Generic helper to delete a widget and its reference from a list
    def _delete_widget_from_list(self, widget_refs, ref_list):
        """Generic helper to delete a group box widget and its reference from a list."""
        widget_refs["group_box"].deleteLater()
        ref_list.remove(widget_refs)

    # Generic helper to delete a row widget and its reference from a list
    def _delete_row_from_list(self, row_widget, ref_list, ref_dict):
        """Generic helper to delete a row widget and its reference from a list."""
        row_widget.deleteLater()
        ref_list.remove(ref_dict)

    def create_general_tab(self):
        """Creates and populates the 'General & Paths' settings tab."""
        tab = QWidget()
        layout = QFormLayout(tab)
        self.stock_delimiter_edit = QLineEdit()
        self.low_stock_edit = QLineEdit()
        self.templates_path_edit = QLineEdit()
        self.stock_output_path_edit = QLineEdit()
        layout.addRow(QLabel("Stock CSV Delimiter:"), self.stock_delimiter_edit)
        layout.addRow(QLabel("Low Stock Threshold:"), self.low_stock_edit)
        layout.addRow(QLabel("Templates Directory:"), self.templates_path_edit)
        layout.addRow(QLabel("Stock Export Output Directory:"), self.stock_output_path_edit)
        settings = self.config_data.get("settings", {})
        paths = self.config_data.get("paths", {})
        self.stock_delimiter_edit.setText(settings.get("stock_csv_delimiter", ";"))
        self.low_stock_edit.setText(str(settings.get("low_stock_threshold", 10)))
        self.templates_path_edit.setText(paths.get("templates", ""))
        self.stock_output_path_edit.setText(paths.get("output_dir_stock", ""))
        self.tab_widget.addTab(tab, "General & Paths")

    def create_rules_tab(self):
        """Creates the 'Rules' tab for dynamically managing automation rules."""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        add_rule_btn = QPushButton("Add New Rule")
        add_rule_btn.clicked.connect(self.add_rule_widget)
        main_layout.addWidget(add_rule_btn, 0, Qt.AlignLeft)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        scroll_content = QWidget()
        self.rules_layout = QVBoxLayout(scroll_content)
        self.rules_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(scroll_content)
        self.tab_widget.addTab(tab, "Rules")
        for rule_config in self.config_data.get("rules", []):
            self.add_rule_widget(rule_config)

    def add_rule_widget(self, config=None):
        """Adds a new group of widgets for creating/editing a single rule.

        Args:
            config (dict, optional): The configuration for a pre-existing
                rule to load into the widgets. If None, creates a new,
                blank rule.
        """
        if not isinstance(config, dict):
            config = {"name": "New Rule", "match": "ALL", "conditions": [], "actions": []}
        rule_box = QGroupBox()
        rule_layout = QVBoxLayout(rule_box)
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Rule Name:"))
        name_edit = QLineEdit(config.get("name", ""))
        header_layout.addWidget(name_edit)
        delete_rule_btn = QPushButton("Delete Rule")
        header_layout.addWidget(delete_rule_btn)
        rule_layout.addLayout(header_layout)
        conditions_box = QGroupBox("IF")
        conditions_layout = QVBoxLayout(conditions_box)
        match_layout = QHBoxLayout()
        match_layout.addWidget(QLabel("Execute actions if"))
        match_combo = QComboBox()
        match_combo.addItems(["ALL", "ANY"])
        match_combo.setCurrentText(config.get("match", "ALL"))
        match_layout.addWidget(match_combo)
        match_layout.addWidget(QLabel("of the following conditions are met:"))
        match_layout.addStretch()
        conditions_layout.addLayout(match_layout)
        conditions_rows_layout = QVBoxLayout()
        conditions_layout.addLayout(conditions_rows_layout)
        add_condition_btn = QPushButton("Add Condition")
        conditions_layout.addWidget(add_condition_btn, 0, Qt.AlignLeft)
        rule_layout.addWidget(conditions_box)
        actions_box = QGroupBox("THEN perform these actions:")
        actions_layout = QVBoxLayout(actions_box)
        actions_rows_layout = QVBoxLayout()
        actions_layout.addLayout(actions_rows_layout)
        add_action_btn = QPushButton("Add Action")
        actions_layout.addWidget(add_action_btn, 0, Qt.AlignLeft)
        rule_layout.addWidget(actions_box)
        self.rules_layout.addWidget(rule_box)
        widget_refs = {
            "group_box": rule_box,
            "name_edit": name_edit,
            "match_combo": match_combo,
            "conditions_layout": conditions_rows_layout,
            "actions_layout": actions_rows_layout,
            "conditions": [],
            "actions": [],
        }
        self.rule_widgets.append(widget_refs)
        add_condition_btn.clicked.connect(lambda: self.add_condition_row(widget_refs))
        add_action_btn.clicked.connect(lambda: self.add_action_row(widget_refs))
        delete_rule_btn.clicked.connect(lambda: self._delete_widget_from_list(widget_refs, self.rule_widgets))
        for cond_config in config.get("conditions", []):
            self.add_condition_row(widget_refs, cond_config)
        for act_config in config.get("actions", []):
            self.add_action_row(widget_refs, act_config)

    def add_condition_row(self, rule_widget_refs, config=None):
        """Adds a new row of widgets for a single condition within a rule.

        This method now supports dynamic value widgets, allowing for either a
        `QLineEdit` or a `QComboBox` based on the selected field and operator.

        Args:
            rule_widget_refs (dict): A dictionary of widget references for the
                parent rule.
            config (dict, optional): The configuration for a pre-existing
                condition. If None, creates a new, blank condition.
        """
        if not isinstance(config, dict):
            config = {}
        row_layout = QHBoxLayout()
        field_combo = QComboBox()
        if self.filterable_columns:
            field_combo.addItems(self.filterable_columns)

        op_combo = QComboBox()
        delete_btn = QPushButton("X")

        row_layout.addWidget(field_combo)
        row_layout.addWidget(op_combo)

        initial_value = config.get("value", "")

        row_widget = QWidget()
        row_widget.setLayout(row_layout)

        condition_refs = {
            "widget": row_widget,
            "field": field_combo,
            "op": op_combo,
            "value_widget": None,
            "value_layout": row_layout,
        }

        row_layout.addWidget(delete_btn)

        # Set initial field from config *before* connecting signals
        if config.get("field") in self.filterable_columns:
            field_combo.setCurrentText(config.get("field"))

        # Connect signals to the new handler
        field_combo.currentTextChanged.connect(
            lambda text: self._on_rule_field_changed(text, condition_refs, config)
        )
        op_combo.currentTextChanged.connect(
            lambda: self._on_rule_op_changed(condition_refs, initial_value)
        )

        # Trigger the first update to populate operators and value widget
        self._on_rule_field_changed(field_combo.currentText(), condition_refs, config)

        rule_widget_refs["conditions_layout"].addWidget(row_widget)
        rule_widget_refs["conditions"].append(condition_refs)
        delete_btn.clicked.connect(
            lambda: self._delete_row_from_list(row_widget, rule_widget_refs["conditions"], condition_refs)
        )

    def _on_rule_field_changed(self, field, condition_refs, config=None):
        """Handler for when the rule's field is changed. Updates the operator list."""
        if config is None:
            config = {}

        op_combo = condition_refs["op"]
        current_op = op_combo.currentText()
        op_combo.blockSignals(True)
        op_combo.clear()

        # Populate operators based on field type
        if field in self.numeric_columns:
            operators = self.OPERATORS_BY_TYPE["numeric"] + self.OPERATORS_BY_TYPE["general"]
        else:
            operators = self.OPERATORS_BY_TYPE["text"] + self.OPERATORS_BY_TYPE["general"]
        op_combo.addItems(operators)

        # Restore previous operator if it's still valid, otherwise set from config
        config_op = config.get("operator")
        if config_op in operators:
            op_combo.setCurrentText(config_op)
        elif current_op in operators:
            op_combo.setCurrentText(current_op)

        op_combo.blockSignals(False)

        # Manually trigger the operator-changed handler to update the value widget
        self._on_rule_op_changed(condition_refs, config.get("value", ""))


    def _on_rule_op_changed(self, condition_refs, initial_value=None):
        """Dynamically changes the rule's value widget based on the selected operator."""
        field = condition_refs["field"].currentText()
        op = condition_refs["op"].currentText()

        # Remove the old value widget, if it exists
        if condition_refs["value_widget"]:
            condition_refs["value_widget"].deleteLater()
            condition_refs["value_widget"] = None

        # Operators that don't need a value input
        if op in ["is empty", "is not empty"]:
            return

        # Determine if a ComboBox should be used for the value
        use_combobox = (
            op in ["equals", "does not equal"]
            and not self.analysis_df.empty
            and field in self.analysis_df.columns
        )

        if use_combobox:
            unique_values = get_unique_column_values(self.analysis_df, field)
            new_widget = QComboBox()
            new_widget.addItems([""] + unique_values)
            if initial_value and str(initial_value) in unique_values:
                new_widget.setCurrentText(str(initial_value))
        else:
            # Default to QLineEdit
            new_widget = QLineEdit()
            new_widget.setPlaceholderText("Value")
            if initial_value is not None:
                new_widget.setText(str(initial_value))

        # Insert the new widget into the layout at the correct position
        condition_refs["value_layout"].insertWidget(2, new_widget, 1)
        condition_refs["value_widget"] = new_widget


    def add_action_row(self, rule_widget_refs, config=None):
        """Adds a new row of widgets for a single action within a rule.

        Args:
            rule_widget_refs (dict): A dictionary of widget references for the
                parent rule.
            config (dict, optional): The configuration for a pre-existing
                action. If None, creates a new, blank action.
        """
        if not isinstance(config, dict):
            config = {}
        row_layout = QHBoxLayout()
        type_combo = QComboBox()
        type_combo.addItems(self.ACTION_TYPES)
        value_edit = QLineEdit()
        delete_btn = QPushButton("X")
        row_layout.addWidget(type_combo)
        row_layout.addWidget(value_edit, 1)
        row_layout.addWidget(delete_btn)
        type_combo.setCurrentText(config.get("type", self.ACTION_TYPES[0]))
        value_edit.setText(config.get("value", ""))
        row_widget = QWidget()
        row_widget.setLayout(row_layout)
        rule_widget_refs["actions_layout"].addWidget(row_widget)
        action_refs = {"widget": row_widget, "type": type_combo, "value": value_edit}
        rule_widget_refs["actions"].append(action_refs)
        delete_btn.clicked.connect(
            lambda: self._delete_row_from_list(row_widget, rule_widget_refs["actions"], action_refs)
        )

    def create_packing_lists_tab(self):
        """Creates the 'Packing Lists' tab for managing report configurations."""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        add_btn = QPushButton("Add New Packing List")
        add_btn.clicked.connect(self.add_packing_list_widget)
        main_layout.addWidget(add_btn, 0, Qt.AlignLeft)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        scroll_content = QWidget()
        self.packing_lists_layout = QVBoxLayout(scroll_content)
        self.packing_lists_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(scroll_content)
        self.tab_widget.addTab(tab, "Packing Lists")
        for pl_config in self.config_data.get("packing_lists", []):
            self.add_packing_list_widget(pl_config)

    def add_packing_list_widget(self, config=None):
        """Adds a new group of widgets for a single packing list configuration.

        Args:
            config (dict, optional): The configuration for a pre-existing
                packing list. If None, creates a new, blank one.
        """
        if not isinstance(config, dict):
            config = {"name": "", "output_filename": "", "filters": [], "exclude_skus": []}
        pl_box = QGroupBox()
        pl_layout = QVBoxLayout(pl_box)
        form_layout = QFormLayout()
        name_edit = QLineEdit(config.get("name", ""))
        filename_edit = QLineEdit(config.get("output_filename", ""))
        exclude_skus_edit = QLineEdit(",".join(config.get("exclude_skus", [])))
        form_layout.addRow("Name:", name_edit)
        form_layout.addRow("Output Filename:", filename_edit)
        form_layout.addRow("Exclude SKUs (comma-separated):", exclude_skus_edit)
        pl_layout.addLayout(form_layout)
        filters_box = QGroupBox("Filters")
        filters_layout = QVBoxLayout(filters_box)
        filters_rows_layout = QVBoxLayout()
        filters_layout.addLayout(filters_rows_layout)
        add_filter_btn = QPushButton("Add Filter")
        filters_layout.addWidget(add_filter_btn, 0, Qt.AlignLeft)
        pl_layout.addWidget(filters_box)
        delete_btn = QPushButton("Delete Packing List")
        pl_layout.addWidget(delete_btn, 0, Qt.AlignRight)
        self.packing_lists_layout.addWidget(pl_box)
        widget_refs = {
            "group_box": pl_box,
            "name": name_edit,
            "filename": filename_edit,
            "exclude_skus": exclude_skus_edit,
            "filters_layout": filters_rows_layout,
            "filters": [],
        }
        self.packing_list_widgets.append(widget_refs)
        add_filter_btn.clicked.connect(
            lambda: self.add_filter_row(widget_refs)
        )
        delete_btn.clicked.connect(lambda: self._delete_widget_from_list(widget_refs, self.packing_list_widgets))
        for f_config in config.get("filters", []):
            self.add_filter_row(widget_refs, f_config)

    def add_filter_row(self, parent_widget_refs, config=None):
        """Adds a new row of widgets for a single filter criterion.

        This is a generic helper used by both packing list and stock export tabs.

        Args:
            parent_widget_refs (dict): Widget references for the parent report.
            config (dict, optional): The configuration for a pre-existing
                filter. If None, creates a new, blank filter.
        """
        if not isinstance(config, dict):
            config = {}
        row_layout = QHBoxLayout()
        field_combo = QComboBox()
        if self.filterable_columns:
            field_combo.addItems(self.filterable_columns)

        op_combo = QComboBox()
        op_combo.addItems(self.FILTER_OPERATORS) # Filters use a simpler, static list of operators
        delete_btn = QPushButton("X")

        row_layout.addWidget(field_combo)
        row_layout.addWidget(op_combo)

        if config.get("field") in self.filterable_columns:
            field_combo.setCurrentText(config.get("field"))
        if config.get("operator") in self.FILTER_OPERATORS:
            op_combo.setCurrentText(config.get("operator"))

        val = config.get("value", "")

        row_widget = QWidget()
        row_widget.setLayout(row_layout)

        filter_refs = {
            "widget": row_widget,
            "field": field_combo,
            "op": op_combo,
            "value_widget": None,
            "value_layout": row_layout,
        }

        # Connect signals to trigger updates on the value widget
        field_combo.currentTextChanged.connect(lambda: self._on_filter_criteria_changed(filter_refs))
        op_combo.currentTextChanged.connect(lambda: self._on_filter_criteria_changed(filter_refs))

        # Set initial widget and value
        self._on_filter_criteria_changed(filter_refs, initial_value=val)

        row_layout.addWidget(delete_btn)
        parent_widget_refs["filters_layout"].addWidget(row_widget)
        parent_widget_refs["filters"].append(filter_refs)
        delete_btn.clicked.connect(
            lambda: self._delete_row_from_list(row_widget, parent_widget_refs["filters"], filter_refs)
        )

    def _on_filter_criteria_changed(self, filter_refs, initial_value=None):
        """Dynamically changes the filter's value widget based on other selections.

        For example, if the operator is '==' and the field is 'Order_Type',
        this method will create a QComboBox with unique values from the
        DataFrame ('Single', 'Multi') instead of a plain QLineEdit.

        Args:
            filter_refs (dict): A dictionary of widget references for the filter row.
            initial_value (any, optional): The value to set in the newly
                created widget. Defaults to None.
        """
        field = filter_refs["field"].currentText()
        op = filter_refs["op"].currentText()

        if filter_refs["value_widget"]:
            filter_refs["value_widget"].deleteLater()

        use_combobox = op in ["==", "!="] and not self.analysis_df.empty and field in self.analysis_df.columns

        if use_combobox:
            try:
                unique_values = self.analysis_df[field].dropna().unique().tolist()
                unique_values = sorted([str(v) for v in unique_values])
                new_widget = QComboBox()
                new_widget.addItems(unique_values)
                if initial_value and str(initial_value) in unique_values:
                    new_widget.setCurrentText(str(initial_value))
            except Exception:
                new_widget = QLineEdit()
                new_widget.setText(str(initial_value) if initial_value else "")
        else:
            new_widget = QLineEdit()
            placeholder = "Value"
            if op in ["in", "not in"]:
                placeholder = "Values, comma-separated"
            new_widget.setPlaceholderText(placeholder)
            text_value = ",".join(initial_value) if isinstance(initial_value, list) else (initial_value or "")
            new_widget.setText(str(text_value))

        filter_refs["value_layout"].insertWidget(2, new_widget, 1)
        filter_refs["value_widget"] = new_widget

    def create_stock_exports_tab(self):
        """Creates the 'Stock Exports' tab for managing report configurations."""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        add_btn = QPushButton("Add New Stock Export")
        add_btn.clicked.connect(self.add_stock_export_widget)
        main_layout.addWidget(add_btn, 0, Qt.AlignLeft)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        scroll_content = QWidget()
        self.stock_exports_layout = QVBoxLayout(scroll_content)
        self.stock_exports_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(scroll_content)
        self.tab_widget.addTab(tab, "Stock Exports")
        for se_config in self.config_data.get("stock_exports", []):
            self.add_stock_export_widget(se_config)

    def add_stock_export_widget(self, config=None):
        """Adds a new group of widgets for a single stock export configuration.

        Args:
            config (dict, optional): The configuration for a pre-existing
                stock export. If None, creates a new, blank one.
        """
        if not isinstance(config, dict):
            config = {"name": "", "output_filename": "", "filters": []}
        se_box = QGroupBox()
        se_layout = QVBoxLayout(se_box)
        form_layout = QFormLayout()
        name_edit = QLineEdit(config.get("name", ""))
        filename_edit = QLineEdit(config.get("output_filename", ""))
        form_layout.addRow("Name:", name_edit)
        form_layout.addRow("Output Filename:", filename_edit)
        se_layout.addLayout(form_layout)
        filters_box = QGroupBox("Filters")
        filters_layout = QVBoxLayout(filters_box)
        filters_rows_layout = QVBoxLayout()
        filters_layout.addLayout(filters_rows_layout)
        add_filter_btn = QPushButton("Add Filter")
        filters_layout.addWidget(add_filter_btn, 0, Qt.AlignLeft)
        se_layout.addWidget(filters_box)
        delete_btn = QPushButton("Delete Stock Export")
        se_layout.addWidget(delete_btn, 0, Qt.AlignRight)
        self.stock_exports_layout.addWidget(se_box)
        widget_refs = {
            "group_box": se_box,
            "name": name_edit,
            "filename": filename_edit,
            "filters_layout": filters_rows_layout,
            "filters": [],
        }
        self.stock_export_widgets.append(widget_refs)
        add_filter_btn.clicked.connect(
            lambda: self.add_filter_row(widget_refs)
        )
        delete_btn.clicked.connect(lambda: self._delete_widget_from_list(widget_refs, self.stock_export_widgets))
        for f_config in config.get("filters", []):
            self.add_filter_row(widget_refs, f_config)

    def create_mappings_tab(self):
        """Creates the 'Mappings' tab for column and courier name mappings."""
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        # Column Mappings GroupBox
        column_mappings_box = QGroupBox("Column Mappings")
        column_mappings_layout = QVBoxLayout(column_mappings_box)

        # Orders Column Mappings
        orders_box = QGroupBox("Orders CSV")
        orders_layout = QFormLayout(orders_box)
        self.column_mapping_widgets["orders"] = {}
        for key, value in self.config_data["column_mappings"]["orders"].items():
            label = QLabel(f"{key.replace('_', ' ').title()}:")
            line_edit = QLineEdit(value)
            orders_layout.addRow(label, line_edit)
            self.column_mapping_widgets["orders"][key] = line_edit
        column_mappings_layout.addWidget(orders_box)

        # Stock Column Mappings
        stock_box = QGroupBox("Stock CSV")
        stock_layout = QFormLayout(stock_box)
        self.column_mapping_widgets["stock"] = {}
        for key, value in self.config_data["column_mappings"]["stock"].items():
            label = QLabel(f"{key.replace('_', ' ').title()}:")
            line_edit = QLineEdit(value)
            stock_layout.addRow(label, line_edit)
            self.column_mapping_widgets["stock"][key] = line_edit
        column_mappings_layout.addWidget(stock_box)

        main_layout.addWidget(column_mappings_box)

        # Courier Mappings GroupBox
        courier_mappings_box = QGroupBox("Courier Mappings")
        courier_main_layout = QVBoxLayout(courier_mappings_box)

        # Layout for the dynamic rows
        self.courier_mappings_layout = QVBoxLayout()
        courier_main_layout.addLayout(self.courier_mappings_layout)

        add_courier_btn = QPushButton("Add Mapping")
        add_courier_btn.clicked.connect(lambda: self.add_courier_mapping_row())
        courier_main_layout.addWidget(add_courier_btn, 0, Qt.AlignLeft)

        main_layout.addWidget(courier_mappings_box)
        main_layout.addStretch()

        self.tab_widget.addTab(tab, "Mappings")

        # Populate initial courier mappings
        for original, standardized in self.config_data.get("courier_mappings", {}).items():
            self.add_courier_mapping_row(original, standardized)

    def add_courier_mapping_row(self, original_name="", standardized_name=""):
        """Adds a new row for a single courier mapping."""
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)

        original_edit = QLineEdit(original_name)
        original_edit.setPlaceholderText("Original Name")
        standardized_edit = QLineEdit(standardized_name)
        standardized_edit.setPlaceholderText("Standardized Name")
        delete_btn = QPushButton("X")

        row_layout.addWidget(original_edit, 1)
        row_layout.addWidget(standardized_edit, 1)
        row_layout.addWidget(delete_btn)

        self.courier_mappings_layout.addWidget(row_widget)

        row_refs = {
            "widget": row_widget,
            "original": original_edit,
            "standardized": standardized_edit,
        }
        self.courier_mapping_widgets.append(row_refs)

        delete_btn.clicked.connect(
            lambda: self._delete_row_from_list(row_widget, self.courier_mapping_widgets, row_refs)
        )

    def save_settings(self):
        """Saves all settings from the UI back into the config dictionary.

        This method iterates through all the dynamically created widgets on all
        tabs, reads their current values, and reconstructs the `self.config_data`
        dictionary. If successful, it accepts the dialog, allowing the main
        window to retrieve the updated configuration.
        """
        try:
            # General Tab
            self.config_data["settings"]["stock_csv_delimiter"] = self.stock_delimiter_edit.text()
            self.config_data["settings"]["low_stock_threshold"] = int(self.low_stock_edit.text())
            self.config_data["paths"]["templates"] = self.templates_path_edit.text()
            self.config_data["paths"]["output_dir_stock"] = self.stock_output_path_edit.text()

            # Rules Tab
            new_rules = []
            for rule_w in self.rule_widgets:
                conditions = []
                for c in rule_w["conditions"]:
                    value_widget = c.get("value_widget")
                    val = ""
                    if value_widget:
                        if isinstance(value_widget, QComboBox):
                            val = value_widget.currentText()
                        else:
                            val = value_widget.text()

                    conditions.append(
                        {
                            "field": c["field"].currentText(),
                            "operator": c["op"].currentText(),
                            "value": val,
                        }
                    )

                actions = [{"type": a["type"].currentText(), "value": a["value"].text()} for a in rule_w["actions"]]
                new_rules.append(
                    {
                        "name": rule_w["name_edit"].text(),
                        "match": rule_w["match_combo"].currentText(),
                        "conditions": conditions,
                        "actions": actions,
                    }
                )
            self.config_data["rules"] = new_rules

            # Packing Lists & Stock Exports Tabs
            for widget_list, key in [
                (self.packing_list_widgets, "packing_lists"),
                (self.stock_export_widgets, "stock_exports"),
            ]:
                new_items = []
                for item_w in widget_list:
                    filters = []
                    for f in item_w["filters"]:
                        op = f["op"].currentText()
                        value_widget = f["value_widget"]
                        val = value_widget.currentText() if isinstance(value_widget, QComboBox) else value_widget.text()
                        filters.append(
                            {
                                "field": f["field"].currentText(),
                                "operator": op,
                                "value": [v.strip() for v in val.split(",")] if op in ["in", "not in"] else val,
                            }
                        )

                    item_data = {"name": item_w["name"].text(), "filters": filters}
                    if "filename" in item_w:
                        item_data["output_filename"] = item_w["filename"].text()
                    if "exclude_skus" in item_w:
                        item_data["exclude_skus"] = [
                            sku.strip() for sku in item_w["exclude_skus"].text().split(",") if sku.strip()
                        ]
                    if "template" in item_w:
                        item_data["template"] = item_w["template"].text()
                    new_items.append(item_data)
                self.config_data[key] = new_items

            # Mappings Tab
            for key, widget in self.column_mapping_widgets["orders"].items():
                self.config_data["column_mappings"]["orders"][key] = widget.text()
            for key, widget in self.column_mapping_widgets["stock"].items():
                self.config_data["column_mappings"]["stock"][key] = widget.text()

            new_courier_mappings = {}
            for row_ref in self.courier_mapping_widgets:
                original = row_ref["original"].text().strip()
                standardized = row_ref["standardized"].text().strip()
                if original and standardized:
                    new_courier_mappings[original] = standardized
            self.config_data["courier_mappings"] = new_courier_mappings

            self.accept()
        except ValueError:
            QMessageBox.critical(self, "Validation Error", "Low Stock Threshold must be a valid number.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dummy_config = {
        "settings": {"stock_csv_delimiter": ";", "low_stock_threshold": 5},
        "paths": {"templates": "data/templates", "output_dir_stock": "data/output"},
        "rules": [
            {
                "name": "Test Rule",
                "match": "ANY",
                "conditions": [{"field": "SKU", "operator": "contains", "value": "TEST"}],
                "actions": [{"type": "ADD_TAG", "value": "auto_tagged"}],
            }
        ],
        "packing_lists": [
            {
                "name": "Test PL",
                "output_filename": "test.xlsx",
                "filters": [{"field": "Order_Type", "operator": "==", "value": "Single"}],
                "exclude_skus": ["SKU1"],
            }
        ],
        "stock_exports": [
            {
                "name": "Test SE",
                "template": "template.xls",
                "filters": [{"field": "Shipping_Provider", "operator": "==", "value": "DHL"}],
            }
        ],
    }
    dialog = SettingsWindow(None, dummy_config)
    if dialog.exec():
        print("Settings saved:", json.dumps(dialog.config_data, indent=2))
    else:
        print("Cancelled.")
    sys.exit(0)
