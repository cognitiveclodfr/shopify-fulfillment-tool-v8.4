# Shopify Fulfillment Tool

## What is this project?

The Shopify Fulfillment Tool is a desktop application designed to streamline the order fulfillment process for Shopify stores. It helps warehouse managers and logistics personnel to efficiently analyze orders, check stock availability, and generate necessary reports like packing lists and stock exports for various couriers.

The tool provides a clear, color-coded user interface to quickly identify which orders are fulfillable, which are not, and which require special attention (e.g., repeat orders).

## How It Works

The application follows a straightforward workflow:
1.  **Start a Session**: The user creates a new session, which generates a unique, dated folder to store all output reports for the current work cycle.
2.  **Load Data**: The user loads a Shopify orders export CSV and a current inventory/stock CSV file.
3.  **Run Analysis**: The core analysis engine processes the data. It simulates the fulfillment process by prioritizing multi-item orders, checks for previously fulfilled orders, and calculates final stock levels.
4.  **Apply Rules**: A powerful, configurable rule engine automatically tags orders, sets priorities, or changes statuses based on user-defined conditions (e.g., tag all orders going to a specific country).
5.  **Review and Edit**: The results are displayed in an interactive table where the user can manually change an order's fulfillment status, add notes, or remove items.
6.  **Generate Reports**: Once the analysis is finalized, the user can generate various reports, such as filtered packing lists for different couriers or stock export files based on custom templates.

## Main Features

-   **Session-Based Workflow**: All generated reports for a work session are saved in a unique, dated folder.
-   **Order & Stock Analysis**: Load Shopify order exports and current stock files to run a fulfillment simulation.
-   **Interactive Data Table**: View all order lines with fulfillment status, stock levels, and other key details.
    -   **Color-Coded Status**: Green for 'Fulfillable', Red for 'Not Fulfillable', Yellow for 'Repeat Order'.
    -   **Context Menu**: Quickly change an order's status or copy key information like Order Number or SKU.
    -   **Filtering and Sorting**: The main data table can be sorted by any column and filtered by text across all columns or a specific column.
-   **Configurable Rule Engine**: Automate your workflow by creating custom rules in the settings. For example, automatically tag all orders from a specific country or set a high priority for orders over a certain value.
-   **Flexible Report Generation**:
    -   **Packing Lists**: Create multiple, filtered packing lists for different couriers or packing stations.
    -   **Stock Exports**: Generate stock export files (e.g., for couriers) by populating data into pre-defined `.xls` templates.
    -   **Custom Reports**: Build your own one-off reports with a simple report builder UI.
-   **Session Persistence**: Close the app and restore your previous session's data on the next launch.

## Project Structure

A brief overview of the main directories:
-   `shopify_tool/`: Contains the core backend logic for analysis, report generation, and the rule engine.
-   `gui/`: Contains all the PySide6 UI code, including the main window, dialogs, and helper classes for managing the UI and user actions.
-   `tests/`: Contains the test suite for the application, written using pytest.
-   `data/`: Contains templates for reports and serves as the default output location.
-   `config.json`: The default configuration file.

## Configuration

The application's behavior is controlled by a `config.json` file.
-   **Location**: On first launch, a default `config.json` is copied from the project resources to a persistent user data directory (e.g., `%APPDATA%/ShopifyFulfillmentTool` on Windows, `~/.local/share/ShopifyFulfillmentTool` on Linux).
-   **Editing**: You can edit this file directly or through the **Settings** window (⚙️) in the application.
-   **Contents**: The configuration allows you to define:
    -   Required columns for your input files.
    -   Paths for templates and output directories.
    -   The automation rules for the rule engine.
    -   The structure and filters for your standard packing lists and stock exports.

## Installation and Setup (for Developers)

To set up the development environment, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd shopify-fulfillment-tool
    ```

2.  **Create a virtual environment (recommended):**
    This project is tested with Python 3.9+.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    The project uses two requirements files:
    -   `requirements.txt`: For core application dependencies.
    -   `requirements-dev.txt`: For development tools (like pytest and ruff).

    Install both using pip:
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    ```

4.  **Run the application:**
    ```bash
    python gui_main.py
    ```

## Code Style and Linting

This project uses `ruff` for code formatting and linting. The rules are defined in `pyproject.toml`.

-   **To format the code:**
    ```bash
    ruff format .
    ```
-   **To check for linting errors:**
    ```bash
    ruff check .
    ```
