# -*- coding: utf-8 -*-
"""
BOQ Summary helper — numbering generated automatically from order line sequence.

No. Item column logic:
  - Each line_section increments a section counter: 1, 2, 3 … → displayed as "1.0", "2.0"
  - Each line_note inside a section increments a subsection letter: A, B, C …
    → displayed as "1.A", "1.B", "2.A" etc.
  - Sections with NO subsections (notes) display cost on the section row itself.
  - Sections WITH subsections show a header row (no cost) then one row per subsection.

Cost column rules (boq_category_id.name, keyword match, case-insensitive):
  "equipment" / "tool"  → Tools & Equipment
  "labour"   / "labor"  → Labor Cost
  everything else        → Cost of Materials

Footer calculations:
  TDC             = sum of all product line subtotals
  Profit base     = TDC − 1.A subsection total  (Permits & Licensing)
  OCM base        = TDC − 1.A − 1.B totals      (also excl. OSH)
  Profit          = Profit base × 8%
  OCM             = OCM base   × 10.75464234%
  VAT             = (TDC + Profit + OCM) × 12%
  Total Constr.   = TDC + Profit + OCM + VAT
"""

from odoo import fields, models

PROFIT_RATE = 0.08
OCM_RATE = 0.1075464234
VAT_RATE = 0.12

_EQUIPMENT_KW = {'equipment', 'tool', 'tools', 'machinery', 'machine'}
_LABOUR_KW = {'labour', 'labor', 'manpower', 'workforce', 'worker'}


def _col(category_name):
    n = (category_name or '').lower()
    if any(k in n for k in _EQUIPMENT_KW):
        return 'equipment'
    if any(k in n for k in _LABOUR_KW):
        return 'labour'
    return 'material'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    subcontract_scope_with_lines = fields.Boolean(
        string='Subcontract Scope With Lines',
        help='If enabled, the subcontract agreement scope prints subcontracted product lines under each subsection.',
    )

    def _get_boq_summary(self):
        lines = self.order_line.sorted('sequence')

        rows = []

        # Counters
        section_num = 0  # increments on each line_section  → 1, 2, 3 …
        sub_idx = 0  # increments on each line_note      → 0=A, 1=B …

        cur_row = None  # dict currently being accumulated
        first_sub_of_section_1a = None  # reference to 1.A row for profit base
        first_sub_of_section_1b = None  # reference to 1.B row for OCM base

        def _section_row(number_str, name):
            return {
                'number': number_str,
                'name': name,
                'is_section': True,
                'equipment': None,
                'material': None,
                'labour': None,
                'total': None,
            }

        def _cost_row(number_str, name):
            return {
                'number': number_str,
                'name': name,
                'is_section': False,
                'equipment': 0.0,
                'material': 0.0,
                'labour': 0.0,
                'total': 0.0,
            }

        def _flush():
            nonlocal cur_row
            if cur_row is not None:
                rows.append(cur_row)
                cur_row = None

        for line in lines:

            if line.display_type == 'line_section':
                _flush()
                section_num += 1
                sub_idx = 0
                number_str = '{}.0'.format(section_num)
                # Start as a section header; if no notes follow it will be
                # promoted to a cost row when the first product line arrives.
                cur_row = _section_row(number_str, line.name or '')

            elif line.display_type == 'line_note':
                _flush()
                if section_num == 0:
                    # Note before any section — create implicit section 0
                    section_num = 1
                    cur_row = _section_row('1.0', '')
                    rows.append(cur_row)
                    cur_row = None

                letter = chr(ord('A') + sub_idx)
                sub_idx += 1
                number_str = '{}.{}'.format(section_num, letter)
                cur_row = _cost_row(number_str, line.name or '')

                # Track 1.A and 1.B for exclusion bases
                if section_num == 1 and sub_idx == 1:  # first sub of section 1
                    first_sub_of_section_1a = cur_row
                elif section_num == 1 and sub_idx == 2:  # second sub of section 1
                    first_sub_of_section_1b = cur_row

            else:
                # Normal product line
                if cur_row is None:
                    # Products before any section/note
                    section_num += 1
                    cur_row = _cost_row('{}.0'.format(section_num), '')

                # Promote section header row to cost row on first product
                if cur_row['is_section']:
                    cur_row['is_section'] = False
                    cur_row['equipment'] = 0.0
                    cur_row['material'] = 0.0
                    cur_row['labour'] = 0.0
                    cur_row['total'] = 0.0

                cat_name = ''
                if line.product_id and line.product_id.product_tmpl_id.boq_category_id:
                    cat_name = line.product_id.product_tmpl_id.boq_category_id.name or ''

                col = _col(cat_name)
                amount = line.price_subtotal
                cur_row[col] += amount
                cur_row['total'] += amount

        _flush()

        # ── Column totals ────────────────────────────────────────────────────
        total_equipment = sum(r['equipment'] for r in rows if r['equipment'] is not None)
        total_material = sum(r['material'] for r in rows if r['material'] is not None)
        total_labour = sum(r['labour'] for r in rows if r['labour'] is not None)
        tdc = total_equipment + total_material + total_labour

        # ── Exclusion bases ──────────────────────────────────────────────────
        permits_total = first_sub_of_section_1a['total'] if first_sub_of_section_1a else 0.0
        osh_total = first_sub_of_section_1b['total'] if first_sub_of_section_1b else 0.0

        profit_base = tdc - permits_total
        ocm_base = tdc - permits_total - osh_total

        profit = round(profit_base * PROFIT_RATE, 2)
        ocm = round(ocm_base * OCM_RATE, 2)
        vat = round((tdc + profit + ocm) * VAT_RATE, 2)
        total_construction = round(tdc + profit + ocm + vat, 2)

        return {
            'rows': rows,
            'total_equipment': total_equipment,
            'total_material': total_material,
            'total_labour': total_labour,
            'grand_total': tdc,
            'profit_rate': PROFIT_RATE * 100,
            'ocm_rate': OCM_RATE * 100,
            'profit_amount': profit,
            'ocm_amount': ocm,
            'vat_amount': vat,
            'construction_total': total_construction,
        }

    def _get_boq_detailed_estimate(self):
        """Build detailed estimate rows with section/subsection/category hierarchy."""
        self.ensure_one()
        lines = self.order_line.sorted('sequence')
        sections = []
        current_section = None
        current_subsection = None

        def _as_category_list(subsection):
            categories = subsection.pop('categories_map')
            subsection['categories'] = list(categories.values())
            return subsection

        def _flush_subsection():
            nonlocal current_subsection, current_section
            if current_section and current_subsection:
                current_section['subsections'].append(_as_category_list(current_subsection))
                current_subsection = None

        def _flush_section():
            nonlocal current_section
            _flush_subsection()
            if current_section:
                sections.append(current_section)
                current_section = None

        def _ensure_section():
            nonlocal current_section
            if not current_section:
                current_section = {
                    'name': 'GENERAL',
                    'subsections': [],
                    'notes': [],
                    'total': 0.0,
                }

        def _ensure_subsection():
            nonlocal current_subsection
            _ensure_section()
            if not current_subsection:
                current_subsection = {
                    'name': 'GENERAL',
                    'categories_map': {},
                    'subtotal': 0.0,
                }

        for line in lines:
            if line.display_type == 'line_section':
                _flush_section()
                current_section = {
                    'name': line.name or 'SECTION',
                    'subsections': [],
                    'notes': [],
                    'total': 0.0,
                }
                continue

            if line.display_type == 'line_subsection':
                _flush_subsection()
                _ensure_section()
                current_subsection = {
                    'name': line.name or 'SUBSECTION',
                    'categories_map': {},
                    'subtotal': 0.0,
                }
                continue

            if line.display_type == 'line_note':
                _ensure_section()
                if current_subsection:
                    current_subsection.setdefault('notes', []).append(line.name or '')
                else:
                    current_section['notes'].append(line.name or '')
                continue

            _ensure_subsection()
            category_name = 'Uncategorized'
            if line.product_id and line.product_id.product_tmpl_id.boq_category_id:
                category_name = line.product_id.product_tmpl_id.boq_category_id.name or 'Uncategorized'

            category = current_subsection['categories_map'].setdefault(
                category_name,
                {'name': category_name, 'lines': [], 'total': 0.0},
            )

            amount = line.price_subtotal
            detail = {
                'description': line.name or (line.product_id.display_name if line.product_id else ''),
                'qty': line.product_uom_qty,
                'uom': line.product_uom.name if line.product_uom else '',
                'unit_cost': line.price_unit,
                'amount': amount,
            }
            category['lines'].append(detail)
            category['total'] += amount
            current_subsection['subtotal'] += amount
            current_section['total'] += amount

        _flush_section()

        return {
            'sections': sections,
            'found': bool(sections),
            'grand_total': sum(section['total'] for section in sections),
        }

    def _get_subcontract_scope(self):
        """Return subcontracted scope grouped by section/subsection."""
        self.ensure_one()

        sections_map = {}
        section_order = []
        current_section = 'GENERAL'
        current_subsection = 'GENERAL'

        def _ensure(section_name, subsection_name):
            if section_name not in sections_map:
                sections_map[section_name] = {
                    'name': section_name,
                    'subsections': [],
                    'subsections_map': {},
                }
                section_order.append(section_name)

            section = sections_map[section_name]
            if subsection_name not in section['subsections_map']:
                subsection = {
                    'name': subsection_name,
                    'lines': [],
                }
                section['subsections_map'][subsection_name] = subsection
                section['subsections'].append(subsection)

            return section['subsections_map'][subsection_name]

        for line in self.order_line.sorted('sequence'):
            if line.display_type == 'line_section':
                current_section = line.name or 'SECTION'
                current_subsection = 'GENERAL'
                continue

            if line.display_type == 'line_subsection':
                current_subsection = line.name or 'SUBSECTION'
                continue

            if line.display_type:
                continue

            if getattr(line, 'x_supplied_by', False) != 'subcontracted':
                continue

            subsection = _ensure(current_section, current_subsection)
            subsection['lines'].append({
                'name': line.name or (line.product_id.display_name if line.product_id else ''),
                'qty': line.product_uom_qty,
                'uom': line.product_uom.name if line.product_uom else '',
                'unit_price': line.price_unit,
                'amount': line.price_subtotal,
            })

        sections = [sections_map[name] for name in section_order]
        for section in sections:
            section.pop('subsections_map', None)

        return {
            'sections': sections,
            'found': bool(sections),
        }
