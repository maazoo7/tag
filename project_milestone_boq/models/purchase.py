from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PurchaseRequestExt(models.Model):
    _inherit = 'purchase.request'
    _description = 'purchase request modifications for projects'

    sale_order_id = fields.Many2one(comodel_name="sale.order", string="Sale Order")
    project_id = fields.Many2one(comodel_name = "project.project", string="Project")
    task_id = fields.Many2one(comodel_name="project.task", string="Task")



    def button_to_approve(self):
        for rec in self:
            if rec.line_ids and rec.task_id:
                for line in rec.line_ids:
                    matching_link = rec.task_id.product_link_ids.filtered(
                        lambda pl: pl.product_id.id == line.product_id.id
                    )

                    # If product link found
                    if matching_link:
                        cost_subtotal = sum(matching_link.mapped('cost_subtotal'))
                        total_cost = line.product_qty * line.estimated_cost

                        if total_cost > cost_subtotal:
                            # 🔹 Post message in chatter
                            rec.message_post(
                                body=_(
                                    "⚠️ Product <b>%s</b> total cost (%.2f) exceeds "
                                    "the linked task cost subtotal (%.2f)."
                                ) % (line.product_id.display_name, total_cost, cost_subtotal)
                            )
                            _logger.warning(
                                f"Cost exceeded for {line.product_id.display_name}: {total_cost} > {cost_subtotal}"
                            )

                    else:
                        # Optionally log or notify if no match found
                        _logger.info(f"No matching link found for product {line.product_id.display_name}")

        # 🔹 Call original approval logic at the end
        return super(PurchaseRequestExt, self).button_to_approve()

    def action_view_linked_project(self):
        self.ensure_one()
        project_ids = self.env['project.project'].search([
            ('id', '=', self.project_id.id)
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Projects',
            'res_model': 'project.project',
            'view_mode': 'list,form',
            'domain': [('id', 'in', project_ids.ids)],
            'context': {
                'default_project_id': self.project_id.id,
            }
        }

    project_count = fields.Integer(
        string='Project Count',
        compute='_compute_project_count',
        store=True
    )

    @api.depends('project_id')
    def _compute_project_count(self):
        for order in self:
            if order.project_id:
                projects = self.env['project.project'].search([
                    ('id', '=', order.project_id.id)
                ])
                order.project_count = len(projects)
            else:
                order.project_count = 0

    def action_view_linked_so(self):
        self.ensure_one()
        sale_order_ids = self.env['sale.order'].search([
            ('id', '=', self.sale_order_id.id)
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Projects',
            'res_model': 'project.project',
            'view_mode': 'list,form',
            'domain': [('id', 'in', sale_order_ids.ids)],
            'context': {
                'default_sale_order_id': self.sale_order_id.id,
            }
        }

    so_count = fields.Integer(
        string='Sale Order Count',
        compute='_compute_so_count',
        store=True
    )

    @api.depends('sale_order_id')
    def _compute_so_count(self):
        for order in self:
            if order.sale_order_id:
                sale_orders = self.env['sale.order'].search([
                    ('id', '=', order.sale_order_id.id)
                ])
                order.so_count = len(sale_orders)
            else:
                order.so_count = 0

    def action_view_linked_task(self):
        self.ensure_one()
        task_ids = self.env['project.task'].search([
            ('id', '=', self.task_id.id)
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Tasks',
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('id', 'in', task_ids.ids)],
            'context': {
                'default_task_id': self.task_id.id,
            }
        }

    task_count = fields.Integer(
        string='Task Count',
        compute='_compute_task_count',
        store=True
    )

    @api.depends('task_id')
    def _compute_task_count(self):
        for order in self:
            if order.task_id:
                tasks = self.env['project.task'].search([
                    ('id', '=', order.task_id.id)
                ])
                order.task_count = len(tasks)
            else:
                order.task_count = 0

class PurchaseOrderExt(models.Model):
    _inherit = "purchase.order"
    _description = "Purchase order modifications according to project"

    delivery_method = fields.Selection([
        ('vendor', 'Vendor Delivery'),
        ('own_fleet', 'Our Trucks')
    ], string="Delivery Method", default='vendor')

    fleet_id = fields.Many2one(comodel_name="fleet.vehicle", string="Fleet ID")

    date_pickup = fields.Datetime(string="Date Pick up")



    def button_confirm(self):
        res = super().button_confirm()
        _logger.info(f"resssssssssssssss -------- {res}")

        move_line = self.env['stock.picking'].sudo().search([('origin','=',self.name)])

        _logger.info(f"move line {move_line}")
        
        move_line.delivery_method = self.delivery_method
        move_line.fleet_id = self.fleet_id
        move_line.date_pickup = self.date_pickup

        return res

    state = fields.Selection(
        selection_add=[
        ('pending_approval', 'Pending Approval'),
        ('rejected','Rejected'),

    ])

    sale_order_id = fields.Many2one(comodel_name="sale.order", string="Sale Order")
    task_id = fields.Many2one(comodel_name="project.task", string="Task")



    def action_pending_approval(self):
        self.write({'state': 'pending_approval'})

    def action_approve_pending_rfq(self):
        for order in self:
            order.write({'state': 'sent'})
            order.button_confirm()

    def name_get(self):
        res = []
        for order in self:
            name = order.name
            _logger.info(f"name : {order.name} state : {order.state}")
            if order.state == 'pending_approval':
                name = f"{name} (Pending Approval RFQ)"
            res.append((order.id, name))
        return res

    def action_view_linked_project(self):
        self.ensure_one()
        project_ids = self.env['project.project'].search([
            ('id', '=', self.project_id.id)
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Projects',
            'res_model': 'project.project',
            'view_mode': 'list,form',
            'domain': [('id', 'in', project_ids.ids)],
            'context': {
                'default_project_id': self.project_id.id,
            }
        }

    project_count = fields.Integer(
        string='Project Count',
        compute='_compute_project_count',
        store=True
    )

    @api.depends('project_id')
    def _compute_project_count(self):
        for order in self:
            if order.project_id:
                projects = self.env['project.project'].search([
                    ('id', '=', order.project_id.id)
                ])
                order.project_count = len(projects)
            else:
                order.project_count = 0

    def action_view_linked_so(self):
        self.ensure_one()
        sale_order_ids = self.env['sale.order'].search([
            ('id', '=', self.sale_order_id.id)
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Projects',
            'res_model': 'project.project',
            'view_mode': 'list,form',
            'domain': [('id', 'in', sale_order_ids.ids)],
            'context': {
                'default_sale_order_id': self.sale_order_id.id,
            }
        }

    so_count = fields.Integer(
        string='Sale Order Count',
        compute='_compute_so_count',
        store=True
    )

    @api.depends('sale_order_id')
    def _compute_so_count(self):
        for order in self:
            if order.sale_order_id:
                sale_orders = self.env['sale.order'].search([
                    ('id', '=', order.sale_order_id.id)
                ])
                order.so_count = len(sale_orders)
            else:
                order.so_count = 0

    def action_view_linked_task(self):
        self.ensure_one()
        task_ids = self.env['project.task'].search([
            ('id', '=', self.task_id.id)
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Tasks',
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('id', 'in', task_ids.ids)],
            'context': {
                'default_task_id': self.task_id.id,
            }
        }

    task_count = fields.Integer(
        string='Task Count',
        compute='_compute_task_count',
        store=True
    )

    @api.depends('task_id')
    def _compute_task_count(self):
        for order in self:
            if order.task_id:
                tasks = self.env['project.task'].search([
                    ('id', '=', order.task_id.id)
                ])
                order.task_count = len(tasks)
            else:
                order.task_count = 0

class PurchaseOrderLineExt(models.Model):
    _inherit = "purchase.order.line"

    estimated_cost = fields.Monetary(
        string='Estimated Cost',
        currency_field='currency_id',
        help="Estimated cost per unit",
    )

    estimated_qty = fields.Char(string="Estimated QTY", readonly=True)


    # currency_id = fields.Many2one(
    #     'res.currency',
    #     string='Currency',
    #     required=True,
    #     default=lambda self: self.env.company.currency_id
    # )

class CreatePOWizard(models.TransientModel):
    _name = 'create.po.wizard'
    _description = 'Create Purchase Order Wizard'

    partner_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        required=True,
        # domain=[('supplier_rank', '>', 0)],
        help='Select the subcontractor/supplier'
    )

    destination_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        required=True,
        help='Project stock location where items will be delivered'
    )

    line_ids = fields.One2many(
        'create.po.wizard.line',
        'wizard_id',
        string='Order Lines'
    )

    task_id = fields.Many2one(
        'project.task',
        string='Task',
        readonly=True
    )

    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)
        _logger.info(f"self.env.context.get('default_task_id'): {self.env.context.get('default_task_id')}")
        if self.env.context.get('default_task_id'):
            res['task_id'] = self.env.context['default_task_id']

        # Get BOQ IDs from context
        if self.env.context.get('default_boq_ids'):
            boq_ids = self.env.context['default_boq_ids']
            if boq_ids and boq_ids[0][2]:
                boqs = self.env['task.product.link'].browse(boq_ids[0][2])
                lines = []
                for boq in boqs:
                    if boq.product_id and boq.quantity > 0:
                        lines.append((0, 0, {
                            'product_id': boq.product_id.id,
                            'description': boq.description or boq.product_id.name,
                            'product_qty': boq.quantity,
                            'product_uom_id': boq.product_id.uom_id.id,
                            'price_unit': boq.estimated_cost,
                            'task_product_link_id': boq.id,
                        }))
                res['line_ids'] = lines

        return res

    def action_create_po(self):
        """Create Purchase Order with selected items"""
        self.ensure_one()
        _logger.info(f"task id {self}")
        if not self.line_ids:
            raise UserError(_("Please add at least one product line."))

        # Prepare PO lines
        po_lines = []
        for line in self.line_ids:
            po_lines.append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.description,
                'product_qty': line.product_qty,
                'product_uom_id': line.product_uom_id.id,  # Changed from product_uom
                'price_unit': line.price_unit,
                'date_planned': fields.Datetime.now(),
            }))

        # Create Purchase Order
        po_vals = {
            'partner_id': self.partner_id.id,
            'order_line': po_lines,
        }

        _logger.info(f"Creating PO with values: {po_vals}")
        po = self.env['purchase.order'].create(po_vals)

        po.project_id = self.task_id.project_id.id
        po.sale_order_id = self.task_id.project_id.reinvoiced_sale_order_id.id
        po.task_id = self.task_id.id
        po.origin = self.task_id.project_id.reinvoiced_sale_order_id.name

        _logger.info(f"Created PO: {po.name}")

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': po.id,
            'target': 'current',
        }


class CreatePOWizardLine(models.TransientModel):
    _name = 'create.po.wizard.line'
    _description = 'Create PO Wizard Line'

    wizard_id = fields.Many2one(
        'create.po.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    task_product_link_id = fields.Many2one(
        'task.product.link',
        string='Task Product Link',
        readonly=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True
    )

    description = fields.Text(
        string='Description'
    )

    product_qty = fields.Float(
        string='Quantity',
        required=True,
        default=1.0
    )

    product_uom_id = fields.Many2one(
        'uom.uom',
        string='UoM',
        required=True
    )

    price_unit = fields.Float(
        string='Unit Price',
        required=True,
        default=0.0
    )

    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True
    )

    @api.depends('product_qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.product_qty * line.price_unit


class PurchaseRequestLineMakePurchaseOrderItemExt(models.TransientModel):
    _inherit = "purchase.request.line.make.purchase.order.item"

    estimated_cost = fields.Monetary(
        string='Estimated Cost',
        currency_field='currency_id',
        help="Estimated cost per unit",
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )


class StockPickingExt(models.Model):
    _inherit = "stock.picking"

    delivery_method = fields.Selection([
        ('vendor', 'Vendor Delivery'),
        ('own_fleet', 'Our Trucks')
    ], string="Delivery Method", default='vendor')

    fleet_id = fields.Many2one(comodel_name="fleet.vehicle", string="Fleet ID")

    date_pickup = fields.Datetime(string="Date Pick up")







