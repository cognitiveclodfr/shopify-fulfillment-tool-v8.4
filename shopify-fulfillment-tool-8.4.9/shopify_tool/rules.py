import pandas as pd


"""Implements a configurable rule engine to process and modify order data.

This module provides a `RuleEngine` class that can apply a series of
user-defined rules to a pandas DataFrame of order data. Rules are defined in a
JSON or dictionary format and can be used to tag orders, change their status,
set priority, and perform other actions based on a set of conditions.

The core components are:
- **Operator Functions**: A set of functions (_op_equals, _op_contains, etc.)
  that perform the actual comparison for rule conditions.
- **OPERATOR_MAP**: A dictionary that maps user-friendly operator names from
  the configuration (e.g., "contains") to their corresponding function.
- **RuleEngine**: A class that takes a list of rule configurations,
  interprets them, and applies the specified actions to the DataFrame rows
  that match the conditions.
"""

# A mapping from user-friendly operator names to internal function names
OPERATOR_MAP = {
    "equals": "_op_equals",
    "does not equal": "_op_not_equals",
    "contains": "_op_contains",
    "does not contain": "_op_not_contains",
    "is greater than": "_op_greater_than",
    "is less than": "_op_less_than",
    "starts with": "_op_starts_with",
    "ends with": "_op_ends_with",
    "is empty": "_op_is_empty",
    "is not empty": "_op_is_not_empty",
}

# --- Operator Implementations ---


def _op_equals(series_val, rule_val):
    """Returns True where the series value equals the rule value."""
    return series_val == rule_val


def _op_not_equals(series_val, rule_val):
    """Returns True where the series value does not equal the rule value."""
    return series_val != rule_val


def _op_contains(series_val, rule_val):
    """Returns True where the series string contains the rule string (case-insensitive)."""
    # Case-insensitive containment check for strings
    return series_val.str.contains(rule_val, case=False, na=False)


def _op_not_contains(series_val, rule_val):
    """Returns True where the series string does not contain the rule string (case-insensitive)."""
    return ~series_val.str.contains(rule_val, case=False, na=False)


def _op_greater_than(series_val, rule_val):
    """Returns True where the series value is greater than the numeric rule value."""
    return pd.to_numeric(series_val, errors="coerce") > float(rule_val)


def _op_less_than(series_val, rule_val):
    """Returns True where the series value is less than the numeric rule value."""
    return pd.to_numeric(series_val, errors="coerce") < float(rule_val)


def _op_starts_with(series_val, rule_val):
    """Returns True where the series string starts with the rule string."""
    return series_val.str.startswith(rule_val, na=False)


def _op_ends_with(series_val, rule_val):
    """Returns True where the series string ends with the rule string."""
    return series_val.str.endswith(rule_val, na=False)


def _op_is_empty(series_val, rule_val):
    """Returns True where the series value is null or an empty string."""
    return series_val.isnull() | (series_val == "")


def _op_is_not_empty(series_val, rule_val):
    """Returns True where the series value is not null and not an empty string."""
    return series_val.notna() & (series_val != "")


class RuleEngine:
    """Applies a set of configured rules to a DataFrame of order data."""

    def __init__(self, rules_config):
        """Initializes the RuleEngine with a given set of rules.

        Args:
            rules_config (list[dict]): A list of dictionaries, where each
                dictionary represents a single rule. A rule consists of
                conditions and actions.
        """
        self.rules = rules_config

    def apply(self, df):
        """Applies all configured rules to the given DataFrame.

        This is the main entry point for the engine. It iterates through each
        rule, finds all rows in the DataFrame that match the rule's conditions,
        and then executes the rule's actions on those matching rows.

        The DataFrame is modified in place.

        Args:
            df (pd.DataFrame): The order data DataFrame to process.

        Returns:
            pd.DataFrame: The modified DataFrame.
        """
        if not self.rules or not isinstance(self.rules, list):
            return df

        # Create columns for actions if they don't exist
        self._prepare_df_for_actions(df)

        for rule in self.rules:
            # Get a boolean Series indicating which rows match the conditions
            matches = self._get_matching_rows(df, rule)

            # Apply actions to the matching rows
            if matches.any():
                self._execute_actions(df, matches, rule.get("actions", []))

        return df

    def _prepare_df_for_actions(self, df):
        """Ensures the DataFrame has the columns required for rule actions.

        Scans all rules to find out which columns will be modified or created
        by the actions (e.g., 'Priority', 'Status_Note'). If these columns
        do not already exist in the DataFrame, they are created and initialized
        with a default value. This prevents errors when an action tries to
        modify a non-existent column.

        Args:
            df (pd.DataFrame): The DataFrame to prepare.
        """
        # Determine which columns are needed by scanning the actions in all rules
        needed_columns = set()
        for rule in self.rules:
            for action in rule.get("actions", []):
                action_type = action.get("type", "").upper()
                if action_type == "SET_PRIORITY":
                    needed_columns.add("Priority")
                elif action_type == "EXCLUDE_FROM_REPORT":
                    needed_columns.add("_is_excluded")
                elif action_type == "EXCLUDE_SKU":
                    needed_columns.add("Status_Note")
                elif action_type == "ADD_TAG":
                    needed_columns.add("Status_Note")

        # Add only the necessary columns if they don't already exist
        if "Priority" in needed_columns and "Priority" not in df.columns:
            df["Priority"] = "Normal"
        if "_is_excluded" in needed_columns and "_is_excluded" not in df.columns:
            df["_is_excluded"] = False
        if "Status_Note" in needed_columns and "Status_Note" not in df.columns:
            df["Status_Note"] = ""

    def _get_matching_rows(self, df, rule):
        """Evaluates a rule's conditions and finds all matching rows.

        Combines the results of each individual condition in a rule using
        either "AND" (all conditions must match) or "OR" (any condition can
        match) logic, as specified by the rule's 'match' property.

        Args:
            df (pd.DataFrame): The DataFrame to evaluate.
            rule (dict): The rule dictionary containing the conditions.

        Returns:
            pd.Series[bool]: A boolean Series with the same index as the
                DataFrame, where `True` indicates a row matches the rule's
                conditions.
        """
        match_type = rule.get("match", "ALL").upper()
        conditions = rule.get("conditions", [])

        if not conditions:
            return pd.Series([False] * len(df), index=df.index)

        # Get a boolean Series for each individual condition
        condition_results = []
        for cond in conditions:
            field = cond.get("field")
            operator = cond.get("operator")
            value = cond.get("value")

            if not all([field, operator, field in df.columns, operator in OPERATOR_MAP]):
                continue

            op_func_name = OPERATOR_MAP[operator]
            op_func = globals()[op_func_name]
            condition_results.append(op_func(df[field], value))

        if not condition_results:
            return pd.Series([False] * len(df), index=df.index)

        # Combine the individual condition results based on the match type
        if match_type == "ALL":
            # ALL (AND logic)
            return pd.concat(condition_results, axis=1).all(axis=1)
        else:
            # ANY (OR logic)
            return pd.concat(condition_results, axis=1).any(axis=1)

    def _execute_actions(self, df, matches, actions):
        """Executes a list of actions on the matching rows of the DataFrame.

        Applies the specified actions (e.g., adding a tag, setting a status)
        to the rows of the DataFrame that are marked as `True` in the `matches`
        Series.

        Args:
            df (pd.DataFrame): The DataFrame to be modified.
            matches (pd.Series[bool]): A boolean Series indicating which rows
                to apply the actions to.
            actions (list[dict]): A list of action dictionaries to execute.
        """
        for action in actions:
            action_type = action.get("type", "").upper()
            value = action.get("value")

            if action_type == "ADD_TAG":
                # Per user feedback, ADD_TAG should modify Status_Note, not Tags
                current_notes = df.loc[matches, "Status_Note"].fillna("").astype(str)

                # Append new tag, handling empty notes and preventing duplicates
                def append_note(note):
                    if value in note.split(", "):
                        return note
                    return f"{note}, {value}" if note else value

                new_notes = current_notes.apply(append_note)
                df.loc[matches, "Status_Note"] = new_notes

            elif action_type == "SET_STATUS":
                df.loc[matches, "Order_Fulfillment_Status"] = value

            elif action_type == "SET_PRIORITY":
                df.loc[matches, "Priority"] = value

            elif action_type == "EXCLUDE_FROM_REPORT":
                df.loc[matches, "_is_excluded"] = True

            elif action_type == "EXCLUDE_SKU":
                # This is a complex, destructive action.
                # For now, we will just mark it for potential later processing.
                # A full implementation would require re-evaluating the entire order.
                # A simple approach is to set its quantity to 0 and flag it.
                if "SKU" in df.columns and "Quantity" in df.columns:
                    sku_to_exclude = value
                    # We need to find rows that match the rule AND the SKU
                    sku_matches = df["SKU"] == sku_to_exclude
                    final_matches = matches & sku_matches
                    df.loc[final_matches, "Quantity"] = 0
                    df.loc[final_matches, "Status_Note"] = df.loc[final_matches, "Status_Note"] + " SKU_EXCLUDED"
