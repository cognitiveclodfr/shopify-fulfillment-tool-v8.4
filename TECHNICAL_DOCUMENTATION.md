# Technical Documentation: Shopify Fulfillment Tool

This document provides a complete technical overview of the Shopify Fulfillment Tool, intended for developers and maintainers. It covers the application's architecture, configuration structure, core logic, and data flow.

## 1. Architecture Overview

The application is a desktop program built with Python, using **PySide6** for the user interface and **pandas** for data manipulation. It is designed to be packaged into a single executable using PyInstaller.

The architecture is divided into two main components:
-   **Backend Logic (`shopify_tool/`)**: A package containing all the core data processing, analysis, and report generation logic. It is designed to be independent of the user interface and can be used as a standalone library.
-   **Frontend GUI (`gui/` and `gui_main.py`)**: The user-facing part of the application that provides controls for loading data, running analysis, and managing settings. It acts as a client to the `shopify_tool` backend.

### Data Flow

The general data flow is as follows:

1.  **Configuration Loading**: On startup, `gui_main.py` loads the `config.json` file from the user's persistent data directory. The user selects an active **Profile**.
2.  **User Input**: The user selects an orders CSV and a stock CSV file through the GUI.
3.  **Validation**: The application validates the headers of the CSV files against the **Column Mappings** defined in the active profile.
4.  **Analysis**: The user clicks "Run Analysis".
    -   `gui_main.py` calls `shopify_tool.core.run_full_analysis()`.
    -   The `core` module reads the CSVs, applies **Courier Mappings**, and runs the main fulfillment simulation logic from `shopify_tool.analysis`.
    -   The `core` module then applies the **Rule Engine** (`shopify_tool.rules`) to the analysis results.
    -   The final `pandas.DataFrame` is returned to the GUI.
5.  **Display**: The GUI displays the DataFrame in an interactive table.
6.  **Report Generation**:
    -   The user requests a report (Packing List or Stock Export).
    -   The GUI calls the appropriate function in `shopify_tool.core` (`create_packing_list_report` or `create_stock_export_report`), passing the relevant report configuration from the active profile.
    -   The `core` module uses `shopify_tool.packing_lists` or `shopify_tool.stock_export` to filter the DataFrame and generate the final Excel file.

## 2. Configuration File (`config.json`)

The `config.json` file is the heart of the application's user-defined settings. All settings are stored within **profiles**.

### Profile Structure

The root of `config.json` contains a `profiles` object and a key for the `active_profile_name`.

```json
{
  "active_profile_name": "My_Warehouse",
  "profiles": {
    "default": { ... },
    "My_Warehouse": { ... }
  }
}
```

Each profile object contains the following keys:

-   `settings`: General application settings.
-   `paths`: Default file paths.
-   `column_mappings`: Defines how user CSV columns map to internal data fields.
-   `courier_mappings`: Standardizes courier names.
-   `rules`: A list of automation rules for the Rule Engine.
-   `packing_lists`: A list of templates for packing list reports.
-   `stock_exports`: A list of templates for stock export reports.

**Example Profile Snippet:**
```json
"My_Warehouse": {
  "settings": {
    "stock_csv_delimiter": ";",
    "low_stock_threshold": 10
  },
  "column_mappings": {
    "orders": { "sku": "Lineitem sku", ... },
    "stock": { "sku": "Артикул", "stock": "Наличност" }
  },
  "courier_mappings": {
    "DHL Express": "DHL"
  },
  "rules": [
    {
      "name": "Prioritize High-Value Orders",
      "match": "ALL",
      "conditions": [
        { "field": "Total Price", "operator": "is greater than", "value": "150" }
      ],
      "actions": [
        { "type": "SET_PRIORITY", "value": "High" }
      ]
    }
  ],
  "packing_lists": [ ... ]
}
```

## 3. Backend Deep Dive (`shopify_tool/`)

### `core.py`
This module acts as the main API for the backend. It orchestrates the other backend modules and is the primary entry point for the GUI.
-   `run_full_analysis()`: The main workflow function. It takes file paths and configurations, manages data validation and cleaning (including applying mappings), calls the analysis function, applies the rule engine, and returns the final DataFrame.
-   `create_packing_list_report()`, `create_stock_export_report()`: These functions take the analysis DataFrame and a specific report configuration, and call the appropriate module to generate the file.

### `analysis.py`
Contains the pure business logic for the fulfillment simulation.
-   `run_analysis()`: Takes clean DataFrames for orders and stock. It determines which orders are fulfillable based on available stock, prioritizing multi-item orders over single-item orders to maximize the number of completed orders.
-   `toggle_order_fulfillment()`: Contains the logic to manually mark an order as "Fulfillable" or "Not Fulfillable" and correctly recalculates the resulting stock changes.

### `rules.py`
Implements the flexible "IF/THEN" rule engine.
-   `RuleEngine` class:
    -   Initialized with a list of rule configurations from the active profile.
    -   The `apply()` method iterates through each rule, evaluates its conditions against the DataFrame, and executes the specified actions on the matching rows.
    -   `OPERATOR_MAP`: A dictionary that maps the string operators from `config.json` (e.g., "contains") to the internal Python functions that perform the comparison.

### `packing_lists.py` & `stock_export.py`
These modules are responsible for generating the final report files.
-   `create_packing_list()`: Takes the main DataFrame and a report configuration. It dynamically builds a pandas query string from the `filters` list, applies it to the DataFrame, excludes any specified SKUs, sorts the results for optimal picking, and formats the output into a clean Excel file using `xlsxwriter`.

## 4. GUI Deep Dive (`gui/` & `gui_main.py`)

### `gui_main.py`
This is the main entry point of the application. It contains the `MainWindow` (or equivalent) class that builds the main UI and manages the application's state.
-   **State Management**: It holds the application's state, including the loaded `config.json`, the name of the `active_profile`, and the main `analysis_df`.
-   **Profile Management**:
    -   `load_config()`: Loads `config.json` from disk.
    -   `save_config()`: Saves the current configuration back to `config.json`.
    -   `create_profile()`: Creates a new profile by deep copying an existing one.
    -   `rename_profile()`, `delete_profile()`: Manages profile names and deletion.
    -   `set_active_profile()`: The core function for switching profiles. It updates the `active_profile_name` in the config and reloads the entire UI to reflect the settings of the newly activated profile.
-   **Backend Interaction**: It calls the functions in `shopify_tool.core` to perform analysis and generate reports, passing the settings from the active profile.

### `gui/settings_window_pyside.py`
This module defines the `SettingsWindow`, a complex dialog that allows users to edit all settings within a profile.
-   **Dynamic UI**: The window is built dynamically based on the configuration of the active profile passed to it.
-   **Data Handling**: It receives a *deep copy* of the active profile's configuration. This ensures that changes are not applied to the main application's state unless the user explicitly clicks "Save."
-   `save_settings()`: When the user clicks "Save," this method reads the state of every widget in the dialog (text boxes, dropdowns, etc.) and reconstructs the configuration dictionary. It then calls `self.accept()`, and `gui_main.py` retrieves the updated dictionary to save to disk.

### `gui/profile_manager_dialog.py`
Provides the UI for managing profiles. It's a simple dialog that calls the profile management methods (`create_profile`, etc.) on its parent, the `MainWindow`.
