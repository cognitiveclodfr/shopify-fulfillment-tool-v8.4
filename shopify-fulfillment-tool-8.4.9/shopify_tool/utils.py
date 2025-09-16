import os
import sys
import logging

logger = logging.getLogger("ShopifyToolLogger")


def get_persistent_data_path(filename):
    """Gets the full path to a file in a persistent application data directory.

    This function provides a reliable way to store application data (like
    history or configuration files) in a user-specific, persistent location.
    It creates the application-specific directory if it does not already exist.

    - On Windows, it uses the `%APPDATA%` environment variable.
    - On other platforms (Linux, macOS), it uses the user's home directory (`~`).

    If the directory cannot be created (e.g., due to permissions), it logs an
    error and defaults to using the current working directory as a fallback.

    Args:
        filename (str): The name of the file to be stored (e.g.,
            "history.csv").

    Returns:
        str: The absolute path to the file within the application's data
             directory.
    """
    # Use APPDATA for Windows, or user's home directory for other platforms
    app_data_path = os.getenv("APPDATA") or os.path.expanduser("~")
    app_dir = os.path.join(app_data_path, "ShopifyFulfillmentTool")

    try:
        os.makedirs(app_dir, exist_ok=True)
    except OSError as e:
        # Fallback to current directory if AppData is not writable
        logger.error(f"Could not create AppData directory: {e}. Falling back to local directory.")
        app_dir = "."

    return os.path.join(app_dir, filename)


def resource_path(relative_path):
    """Gets the absolute path to a resource, for both dev and PyInstaller.

    When an application is bundled with PyInstaller, its resources (like icons
    or data files) are stored in a temporary directory. The path to this
    directory is available in `sys._MEIPASS`.

    This function checks for the `_MEIPASS` attribute. If it exists, the path
    is constructed relative to it. If not (i.e., when running in a normal
    development environment), it constructs the path relative to the project's
    root directory.

    Args:
        relative_path (str): The path to the resource relative to the
            application root (e.g., "data/templates/template.xls").

    Returns:
        str: The absolute path to the resource, suitable for the current
             execution environment.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
