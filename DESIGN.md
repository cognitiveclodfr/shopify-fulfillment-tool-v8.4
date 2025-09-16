# Visual Design Guideline

This document outlines the visual design principles for the Shopify Fulfillment Tool to ensure a consistent, modern, and professional user interface.

## 1. Color Palette (Dark Theme)

The application uses a dark theme. The color palette is designed for clarity and comfort during prolonged use.

| Role                  | Hex Code  | Description                                           |
| --------------------- | --------- | ----------------------------------------------------- |
| **Accent / Primary**  | `#3B82F6` | For primary buttons, links, and selected items.       |
| **Destructive**       | `#EF4444` | For delete buttons and critical warnings. **Should always be used with a confirmation dialog.** |
| **Success**           | `#22C55E` | For success indicators and positive feedback.         |
| **Warning**           | `#F97316` | For non-critical warnings and alerts.                 |
| **Info**              | `#60A5FA` | For informational icons and messages.                 |
|                       |           |                                                       |
| **Background**        | `#2B2B2B` | Main background color for windows and frames.         |
| **Background Subtle** | `#3C3F41` | For elements that need to be slightly elevated, like entries or tab views. |
| **Foreground**        | `#FFFFFF` | Primary text color.                                   |
| **Foreground Muted**  | `#A9B7C6` | For secondary text, labels, and disabled elements.    |
| **Border**            | `#555555` | For borders around frames and interactive elements.   |
| **Highlight**         | `#F0E68C` | For highlighting specific rows or data points, e.g., 'Repeat' orders. |


## 2. Component-Specific Design Notes

- **Data Table Highlighting:** To draw attention to important information in the main analysis table, rows with a `System_note` (such as 'Repeat' orders) are highlighted. This is achieved by setting the row's background color to the **Highlight** color (`#F0E68C`). The foreground text color should remain readable against this background.

## 3. Typography

We use the system's default UI font for consistency across platforms (e.g., Segoe UI on Windows, San Francisco on macOS).

| Element               | Font Size | Weight | Usage Example                               |
| --------------------- | --------- | ------ | ------------------------------------------- |
| **Window Title**      | 18pt      | Bold   | "Shopify Fulfillment Tool"                  |
| **Page/Tab Title**    | 16pt      | Bold   | "General Settings", "Packing Lists"         |
| **Label / Subheading**| 14pt      | Normal | "Stock CSV Delimiter:", "Filters:"           |
| **Body / Entry Text** | 12pt      | Normal | Text inside input fields and table cells.   |
| **Caption / Tooltip** | 10pt      | Normal | Small helper text, tooltips.                |

## 4. Spacing & Padding

A consistent spacing system improves readability and layout harmony. We use a base unit of **5px**.

- **Outer Padding (Window/Large Frames):** `10px` (`padx=10`, `pady=10`)
- **Inner Padding (Inside Frames):** `5px` (`padx=5`, `pady=5`)
- **Widget Spacing (Between buttons, labels, etc.):** `5px` to `10px` depending on grouping.

## 5. Corner Radius

- **Buttons & Entries:** `6px` (or customtkinter default)
- **Frames & Tabs:** `8px` (or customtkinter default)

## 6. Icons

A consistent and modern set of icons will be used for actions and statuses.
- **Source:** We will use icons from a professional library like **Feather Icons** or **Material Design Icons**.
- **Format:** Icons should be in SVG or high-resolution PNG format.
- **Storage:** Icons will be stored in a dedicated `assets/icons/` directory.
- **Usage:**
  - **Info:** `info.svg`
  - **Warning:** `alert-triangle.svg`
  - **Error:** `alert-circle.svg`
  - **Delete:** `trash-2.svg`
  - **Add:** `plus.svg`
  - **Settings:** `settings.svg`
  - **Edit:** `edit.svg`
  - **Copy:** `copy.svg`
