import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging():
    """Configures and initializes the logging for the entire application.

    This function sets up a centralized logger named 'ShopifyToolLogger'.
    It configures two handlers:
    1.  **RotatingFileHandler**: Writes log messages of level INFO and above to
        a file named `logs/app_history.log`. The log file is rotated when it
        reaches 1MB, and up to 5 backup files are kept. This is for persistent
        historical logging.
    2.  **StreamHandler**: Writes log messages of level INFO and above to the
        console (stderr). This is useful for immediate feedback during
        development or for headless execution.

    The function ensures that handlers are not duplicated if it is called
    multiple times. A specific handler for the GUI is expected to be added
    separately by the UI code.

    Returns:
        logging.Logger: The configured logger instance for the application.
    """
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, "app_history.log")

    # Get the root logger used by the application
    logger = logging.getLogger("ShopifyToolLogger")
    logger.setLevel(logging.INFO)  # Set the lowest level to capture all messages

    # Prevent adding handlers multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a handler for writing to a file
    file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setLevel(logging.INFO)  # Log everything to the file
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # The UI handler will be added separately in the GUI code
    # We add a basic StreamHandler for non-GUI execution or debugging
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_formatter = logging.Formatter("%(levelname)s: %(message)s")
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)

    return logger
