from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PySide6.QtGui import QColor
import pandas as pd


class PandasModel(QAbstractTableModel):
    """A Qt model to interface a pandas DataFrame with a QTableView.

    This class acts as a wrapper around a pandas DataFrame, allowing it to be
    displayed and manipulated in a Qt view (like QTableView) while adhering to
    the Qt Model/View programming paradigm.

    It handles data retrieval, header information, and custom styling (e.g.,
    row colors) based on the DataFrame's content.

    Attributes:
        _dataframe (pd.DataFrame): The underlying pandas DataFrame.
        colors (dict): A mapping of status strings to QColor objects for row
                       styling.
    """

    def __init__(self, dataframe: pd.DataFrame, parent=None):
        """Initializes the PandasModel.

        Args:
            dataframe (pd.DataFrame): The pandas DataFrame to be modeled.
            parent (QObject, optional): The parent object. Defaults to None.
        """
        super().__init__(parent)
        self._dataframe = dataframe
        # Define colors for styling
        self.colors = {
            "Fulfillable": QColor("#2E8B57"),  # SeaGreen
            "NotFulfillable": QColor("#B22222"),  # FireBrick
            "SystemNoteHighlight": QColor("#DAA520"),  # GoldenRod
        }

    def rowCount(self, parent=QModelIndex()) -> int:
        """Returns the number of rows in the model."""
        if parent.isValid():
            return 0
        return len(self._dataframe)

    def columnCount(self, parent=QModelIndex()) -> int:
        """Returns the number of columns in the model."""
        if parent.isValid():
            return 0
        return len(self._dataframe.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        """Returns the data for a given model index and role.

        This method is called by the view to get the data to display. It
        handles:
        - `DisplayRole`: The text to be displayed in a cell.
        - `BackgroundRole`: The background color of a row, based on the
          'System_note' or 'Order_Fulfillment_Status' columns.

        Args:
            index (QModelIndex): The index of the item to retrieve data for.
            role (Qt.ItemDataRole): The role for which to retrieve data.

        Returns:
            Any: The data for the given role, or None if not applicable.
        """
        if not index.isValid():
            return None

        row = index.row()

        if role == Qt.ItemDataRole.DisplayRole:
            try:
                value = self._dataframe.iloc[row, index.column()]
                if pd.isna(value):
                    return ""
                return str(value)
            except IndexError:
                return None

        if role == Qt.ItemDataRole.BackgroundRole:
            try:
                # Check for system note first, as it takes precedence
                if (
                    "System_note" in self._dataframe.columns
                    and pd.notna(self._dataframe.iloc[row]["System_note"])
                    and self._dataframe.iloc[row]["System_note"]
                ):
                    return self.colors["SystemNoteHighlight"]

                # Otherwise, color based on fulfillment status
                if "Order_Fulfillment_Status" in self._dataframe.columns:
                    status = self._dataframe.iloc[row]["Order_Fulfillment_Status"]
                    if status == "Fulfillable":
                        return self.colors["Fulfillable"]
                    elif status == "Not Fulfillable":
                        return self.colors["NotFulfillable"]
            except (IndexError, KeyError):
                return None  # In case columns are missing

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        """Returns the header data for the given section and orientation.

        Args:
            section (int): The row or column number.
            orientation (Qt.Orientation): The header orientation (Horizontal
                or Vertical).
            role (Qt.ItemDataRole): The role for which to retrieve data.

        Returns:
            str | None: The header title, or None.
        """
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._dataframe.columns[section])
            if orientation == Qt.Orientation.Vertical:
                return str(section + 1)
        return None

    def get_column_index(self, column_name):
        """Returns the numerical index of a column from its string name.

        Args:
            column_name (str): The name of the column.

        Returns:
            int | None: The index of the column, or None if not found.
        """
        try:
            return self._dataframe.columns.get_loc(column_name)
        except KeyError:
            return None

    def set_column_order_and_visibility(self, all_columns_in_order, visible_columns):
        """Reorders and filters columns in the underlying DataFrame.

        Note: This method seems to be obsolete or not fully implemented, as
        column visibility is now handled by the view/proxy.

        Args:
            all_columns_in_order (list[str]): A list of all column names in
                the desired order.
            visible_columns (list[str]): A list of columns that should remain
                visible.
        """
        self.beginResetModel()
        existing_columns = [col for col in all_columns_in_order if col in self._dataframe.columns]
        self._dataframe = self._dataframe[existing_columns]
        self.hidden_columns = [col for col in all_columns_in_order if col not in visible_columns]
        self.endResetModel()
