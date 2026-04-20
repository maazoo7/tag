# sale_boq_report — Bill of Quantities Report for Odoo 19

## What it does

Adds a **BOQ Report** button to Sale Orders that prints a structured
Bill of Quantities PDF matching the layout in the sample.

It now includes a **Detailed Estimate** page with this structure:
**Section (main) → Subsection → BOQ Category groups → Item lines**,
including **Subsection Totals** and **Section Totals**.

---

## Module structure

```
sale_boq_report/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── sale_order.py          ← Python grouping logic
└── report/
    ├── sale_boq_report_action.xml     ← ir.actions.report
    └── sale_boq_report_template.xml  ← QWeb PDF template
```

---

## Prerequisites — field you must add to product.template

The report groups product lines by **BOQ Category** using:

```python
product_id.product_tmpl_id.boq_category_id
```

You need a Many2one field on `product.template` pointing to a
category model (e.g. a simple `product.boq.category` or you can
reuse an existing model like `product.category`).

### Option A — Reuse product.category (quickest)

In your own module add:

```python
# models/product_template.py
from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    boq_category_id = fields.Many2one(
        'product.category',
        string='BOQ Category',
        help='e.g. Labour, Material, Equipment'
    )
```

### Option B — Dedicated lightweight model

```python
# models/product_boq_category.py
from odoo import fields, models

class ProductBOQCategory(models.Model):
    _name        = 'product.boq.category'
    _description = 'BOQ Category'
    _order       = 'sequence, name'

    name     = fields.Char(required=True)
    sequence = fields.Integer(default=10)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    boq_category_id = fields.Many2one(
        'product.boq.category',
        string='BOQ Category',
    )
```

Add the model name to the `_inherit` chain and register it in
`__manifest__.py` → `depends`.

---

## Sale Order line setup

| display_type   | Role in BOQ                                  |
|----------------|----------------------------------------------|
| `line_section`  | **Main section** header (yellow-green row)   |
| `line_note`     | **Sub-section** header OR plain note (italic)|
| *(normal line)* | Product / labour / equipment item            |

### Sub-section vs plain note logic

- The **first** `line_note` after a section (or after the last subsection's
  products end) is treated as a **sub-section header**.
- Any subsequent notes before products appear are **notes_before** (italic).
- Notes after the last product in a subsection are **notes_after** (italic).
- A note that matches pattern `^[\dA-Z]+\.\s` (e.g. "1.A.1 Building Permit")
  always opens a new subsection.

---

## Cost columns

| Column          | Shown when `boq_category_id.name` contains… |
|-----------------|---------------------------------------------|
| Tools & Equip.  | equipment / tool / machinery                |
| Cost of Materials | material / supply / goods (default)       |
| Labor Cost      | labour / labor / manpower / worker          |
| Total Cost      | **always** shown                            |

The classification is keyword-based (case-insensitive) in
`models/sale_order.py → _classify()`. Adjust keywords as needed.

---

## Installation

```bash
# Copy module into your Odoo addons path
cp -r sale_boq_report /path/to/odoo/addons/

# Restart Odoo and update
./odoo-bin -c odoo.conf -u sale_boq_report
```

Then open any Sale Order → **Print** → **BOQ Report**.

---

## Customisation tips

* **Paper size**: change `ref="base.paperformat_a4"` in the action XML to
  `base.paperformat_us_letter` or your custom paperformat.
* **Logo / header**: the template uses `web.external_layout` which
  automatically picks up the company logo set in Settings → Companies.
* **Amount in words**: uncomment the `amount_in_words` line in the template
  if you have a module that provides that field.
* **Section colours**: edit the inline `background-color` styles in
  `sale_boq_report_template.xml`.
