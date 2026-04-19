from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class CreateInventoryTransferWizard(models.TransientModel):
    _name = 'create.inventory.transfer.wizard'
    _description = 'Wizard to create inventory transfer'

    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        required=True,
        default=lambda self: self.env.context.get('default_warehouse_id')
    )



    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Operation Type',
        required=True,
        domain="[('warehouse_id', '=', warehouse_id)]",
    )

    line_ids = fields.One2many(
        'create.inventory.transfer.line.wizard',
        'wizard_id',
        string='Transfer Lines'
    )

    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)

        _logger.info(f"Context in default_get: {self.env.context}")

        # Get BOQ line IDs from context
        if self.env.context.get('default_boq_line_ids'):
            boq_line_ids_raw = self.env.context['default_boq_line_ids']

            _logger.info(f"Raw boq_line_ids: {boq_line_ids_raw}, type: {type(boq_line_ids_raw)}")

            # Extract actual IDs from various formats
            boq_line_ids = []

            if isinstance(boq_line_ids_raw, list):
                # Check if it's a list of tuples (Odoo command format)
                if boq_line_ids_raw and isinstance(boq_line_ids_raw[0], (tuple, list)):
                    # Format: [(6, 0, [1, 2, 3])] or [(4, id)] or [(0, 0, {...})]
                    for cmd in boq_line_ids_raw:
                        if cmd[0] == 6:  # Set command (6, 0, [ids])
                            boq_line_ids = cmd[2] if len(cmd) > 2 else []
                            break
                        elif cmd[0] == 4:  # Link command (4, id)
                            boq_line_ids.append(cmd[1])
                        elif cmd[0] in (1, 2):  # Update/delete (1, id, {...}) or (2, id)
                            boq_line_ids.append(cmd[1])
                else:
                    # Already a plain list of IDs
                    boq_line_ids = boq_line_ids_raw
            elif isinstance(boq_line_ids_raw, int):
                # Single ID
                boq_line_ids = [boq_line_ids_raw]
            else:
                boq_line_ids = []

            _logger.info(f"Extracted BOQ line IDs: {boq_line_ids}")

            if not boq_line_ids:
                raise UserError(_("No BOQ lines provided."))

            # Browse the records
            boq_lines = self.env['task.product.link'].browse(boq_line_ids)

            # Filter to only existing records
            boq_lines = boq_lines.exists()

            if not boq_lines:
                raise UserError(_("Selected BOQ records not found."))

            lines = []
            for boq_line in boq_lines:
                # Skip if no product or quantity
                if not boq_line.product_id or boq_line.quantity <= 0:
                    _logger.warning(f"Skipping BOQ line {boq_line.id}: no product or invalid quantity")
                    continue

                line_vals = {
                    'product_id': boq_line.product_id.id,
                    'product_uom_qty': boq_line.quantity,
                    'boq_line_id': boq_line.id,
                    'project_warehouse_id' : boq_line.project_warehouse_id.id
                }

                lines.append((0, 0, line_vals))
                _logger.info(f"Added line for product {boq_line.product_id.name}: qty={boq_line.quantity}")

            if not lines:
                raise UserError(_("No valid lines found. Check if products and quantities are set."))

            res['line_ids'] = lines
            _logger.info(f"Created {len(lines)} wizard lines from {len(boq_lines)} BOQ records")

        return res

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        """Update picking type domain when warehouse changes"""
        if self.warehouse_id:
            # Auto-select internal transfer type if available
            internal_type = self.env['stock.picking.type'].search([
                ('warehouse_id', '=', self.warehouse_id.id),
                ('code', '=', 'internal')
            ], limit=1)

            if internal_type:
                self.picking_type_id = internal_type.id

            return {
                'domain': {'picking_type_id': [('warehouse_id', '=', self.warehouse_id.id)]}
            }

    def action_create_transfer(self):
        """Create inventory transfer picking"""
        # Validate wizard has lines
        if not self.line_ids:
            raise UserError(_("Please add at least one product line."))

        # Validate picking type
        if not self.picking_type_id:
            raise UserError(_("Please select an operation type."))

        main_warehouse_id = self.env.context.get('warehouse_id')

        _logger.info(f"Creating transfer from warehouse ID: {main_warehouse_id}")

        main_wh = self.env['stock.warehouse'].browse(main_warehouse_id)

        if not main_wh.exists():
            raise UserError(_("Source warehouse is not defined."))

        # Get destination warehouse from BOQ lines (assumes all share same project warehouse)
        first_boq_line = self.line_ids[0].boq_line_id
        _logger.info(f"first_boq_line {self.line_ids}")
        _logger.info(f"first_boq_line {self.line_ids[0]}")
        _logger.info(f"first_boq_line {first_boq_line}")
        _logger.info(f"first_boq_line warehosiue {first_boq_line.project_warehouse_id}")
        project_wh = first_boq_line.project_warehouse_id

        if not project_wh:
            raise UserError(_("Destination (Project) warehouse is not defined in BOQ records."))

        # Validate warehouses are different
        if main_wh.id == project_wh.id:
            raise UserError(_("Source and destination warehouses cannot be the same."))

        # Create picking
        picking_vals = {
            'picking_type_id': self.picking_type_id.id,
            'location_id': main_wh.lot_stock_id.id,
            'location_dest_id': project_wh.lot_stock_id.id,
            'origin': f"BOQ Transfer - {', '.join(self.line_ids.mapped('boq_line_id').task_id.name or ['Manual'])}",
        }

        picking = self.env['stock.picking'].create(picking_vals)

        # Create stock moves for each line
        move_vals_list = []
        for line in self.line_ids:
            move_vals = {
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_id.uom_id.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
            }
            move_vals_list.append(move_vals)

        # Batch create moves for better performance
        moves = self.env['stock.move'].create(move_vals_list)
        _logger.info(f"Created picking ID: {picking.id} with {len(moves)} moves")

        # Optionally auto-confirm the picking
        # picking.action_confirm()

        return {
            'name': _('Inventory Transfer'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }


class CreateInventoryTransferLineWizard(models.TransientModel):
    _name = 'create.inventory.transfer.line.wizard'
    _description = 'Wizard Lines for Transfer Creation'

    wizard_id = fields.Many2one(
        'create.inventory.transfer.wizard',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True
    )
    product_uom_qty = fields.Float(
        string='Quantity',
        required=True,
        default=1.0
    )
    boq_line_id = fields.Many2one(
        'task.product.link',
        string='BOQ Line'
    )

    # Optional: Add display name for better UX
    display_name = fields.Char(
        string='Description',
        compute='_compute_display_name'
    )

    project_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        required=True,
    )



    @api.depends('product_id', 'product_uom_qty', 'boq_line_id')
    def _compute_display_name(self):
        for line in self:
            if line.product_id:
                line.display_name = f"{line.product_id.name} - {line.product_uom_qty} {line.product_id.uom_id.name}"
            else:
                line.display_name = "New Line"


# class stockPickingExt(models.Model):
#     _inherit = "stock.picking"
#     _description = "stock picking"

