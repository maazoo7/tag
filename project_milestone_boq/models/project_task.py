# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, _
import logging
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.tools.float_utils import float_is_zero


_logger = logging.getLogger(__name__)

class ProjectTask(models.Model):
    _inherit = 'project.task'


    product_link_ids = fields.One2many('task.product.link', 'task_id', string="Linked Products")

    purchase_count = fields.Integer(string="Purchase Count")
    product_count = fields.Integer(compute='_compute_product_count', string="Product Count")

    linked_pr_count = fields.Integer(compute='_get_linked_pr', string="Linked PR")
    linked_po_count = fields.Integer(compute='_get_linked_po', string="Linked PO")
    moves_count = fields.Integer(compute='_get_related_moves', string="Inventory Moves")

    # def _get_related_moves(self):
    #     self.env['stock.picking'].search_count([('task_id', '=', rec.id)])


    @api.depends("product_link_ids")
    def _get_linked_pr(self):
        for rec in self:
            pr_count = self.env['purchase.request'].search_count([('task_id','=',rec.id)])
            po_count = self.env['purchase.order'].search_count([('task_id','=',rec.id)])
            rec.linked_pr_count = pr_count
            rec.linked_po_count = po_count

    @api.depends('product_link_ids')
    def _compute_product_count(self):
        """Compute number of linked products for each task."""
        for task in self:
            task.product_count = len(task.product_link_ids)

    # TODO UPDATE ONCE DONE
    def write(self, vals):
        # res =
        _logger.info(f"vals in tasks {vals}")
        if 'stage_id' in vals and vals['stage_id']:
            stage_id = self.env['project.task.type'].sudo().search([
                ('project_ids' ,'in' , self.project_id.ids),
                ('id', 'in', vals.get('stage_id'))
            ], limit=1)
            _logger.info(f"stage_id {stage_id},{stage_id.fold}")
            if stage_id.fold:
                self.state = '1_done'
            if (stage_id.fold or stage_id.name == 'Done') and not self.qty_consumed:
                raise ValidationError(f"Please complete the consume quantities process")
        return super(ProjectTask, self).write(vals)

    qty_consumed = fields.Boolean(string="Quantity Consumed", default=False, store=True)

    def action_view_linked_products(self):
        action = self.env['ir.actions.act_window']._for_xml_id('project_milestone_boq.project_linked_product_action')

        action['display_name'] = _("%(name)s's Products", name=self.name)

        action['domain'] = [('task_id', '=', self.id)]

        action['context'] = {'default_task_id': self.id}
        action['context'] = {
            'group_by': ['boq_category_id']
        }

        return action

    def action_consume_linked_products(self):
        self.ensure_one()

        # 1. Filter links with consumption > 0
        product_links = self.product_link_ids.filtered(
            lambda l: not float_is_zero(l.consumed_qty, precision_digits=3)
        )


        picking = self.env['stock.picking']

        _logger.info(f"Product Links {product_links}")
        if not product_links:
            raise exceptions.UserError(_("No items are marked for consumption on this task."))

        project_id = self.project_id
        sale_order = self.env['sale.order'].sudo().search([('project_id', '=', project_id.id)], limit=1)
        _logger.info(f"Sale Order ID {sale_order}")
        if not sale_order:
            raise exceptions.UserError(_("This task is not linked to a Sales Order."))

        consumed_lines_log = []

        if not self.qty_consumed:
            for link in product_links:
                qty_to_consume = link.consumed_qty
                _logger.info(f"qty to consuem {qty_to_consume}, {link}")

                sale_line = link.sale_line_id

                if not sale_line:
                    _logger.warning("BOQ item %s is not linked to a Sale Order Line.", link.product_id.name)
                    continue

                if sale_line.product_id.type == 'service':
                    new_delivered_qty = sale_line.qty_delivered + qty_to_consume
                    sale_line.write({'qty_delivered': new_delivered_qty})

                    consumed_lines_log.append(f"- (Service) {link.product_id.name}: {qty_to_consume}")
                    _logger.info(f"- (Service) {link.product_id}: {qty_to_consume}")
                else:

                    if not picking:
                        picking = self.env['stock.picking'].search([
                            ('sale_id', '=', sale_order.id),
                            ('picking_type_code', '=', 'outgoing'),
                            ('state', 'not in', ('done', 'cancel'))
                        ], limit=1)
                        _logger.info(f"Picking values: {picking.name or 'None', picking.id}")

                    if not picking:
                        _logger.error("No pending Delivery Order found for SO %s.", sale_order.name)
                        consumed_lines_log.append(f"- (Inventory) {link.product_id.name}: Failed (No DO)")

                        continue

                    _logger.info(f"ENtering move line")
                    move_line = self.env['stock.move.line'].search([
                        ('picking_id', '=', picking.id),
                        ('move_id.sale_line_id', '=', sale_line.id),
                        ('state', 'not in', ('done', 'cancel'))
                    ], limit=1)
                    _logger.info(f"move line, {move_line}")
                    if move_line:
                        move_line.qty_done += qty_to_consume
                        consumed_lines_log.append(f"- (Inventory) {link.product_id.name}: {qty_to_consume}")
                    else:
                        _logger.warning("No pending Stock Move Line found for SO Line %s.", sale_line.name)
                        consumed_lines_log.append(f"- (Inventory) {link.product_id.name}: Failed (No Move)")
            if picking and picking.state not in ('done', 'cancel'):
                validate_resp = picking.button_validate()
                _logger.info(f"validate res {validate_resp}")

                if isinstance(validate_resp, dict) and validate_resp.get('res_model') == 'stock.backorder.confirmation':
                    backorder_wizard = self.env['stock.backorder.confirmation'].with_context(
                        validate_resp.get('context')).create({})
                    backorder_wizard.process()  # Automatically confirm the backorder
                    _logger.info(f"Backorder created and processed for {picking.name}")
                self.qty_consumed = True
                _logger.info(
                    f"Delivery Order **{picking.name}** updated and validated successfully based on BOQ consumption."
                )

            # if picking and picking.state not in ('done', 'cancel'):
            #     validate_resp = picking.button_validate()
            #     _logger.info(f"validate res {validate_resp}")
            #     _logger.info(
            #         "Delivery Order **%s** updated and validated successfully based on BOQ consumption." % picking.name)
            #     # try:
                #     pass
                # except Exception as e:
                #     _logger.error("Failed to validate picking %s: %s", picking.name, str(e))
                #     _logger.info(
                #         "Delivery Order **%s** partially updated, but failed final validation. Check Inventory." % picking.name)
            # self.qty_consumed = True


    def action_view_linked_pr(self):
        action = self.env['ir.actions.act_window']._for_xml_id('purchase_request.purchase_request_form_action')

        action['display_name'] = _("%(name)s's Products", name=self.name)

        action['domain'] = [('task_id', '=', self.id)]

        action['context'] = {'default_task_id': self.id}


        return action

    def action_view_linked_po(self):
        action = self.env['ir.actions.act_window']._for_xml_id('purchase.purchase_form_action')

        action['display_name'] = _("%(name)s's Products", name=self.name)

        action['domain'] = [('task_id', '=', self.id)]

        action['context'] = {'default_task_id': self.id}


        return action

class ProjectExt(models.Model):
    _inherit = "project.project"

    purchase_count = fields.Integer(string="Purchase Count")

    milestone_count = fields.Integer(
        string='Milestone Count',
        compute='_compute_milestone_count',
        store=False
    )

    linked_pr_count = fields.Integer(compute='_get_linked_pr', string="Linked PR")
    linked_po_count = fields.Integer(compute='_get_linked_po', string="Linked PO")
    moves_count = fields.Integer(compute='_get_related_moves', string="Inventory Moves")

    def _get_related_moves(self):
        for rec in self:
            total_moves = self.env['stock.picking'].search_count([('project_id', '=', rec.id)])
            rec.moves_count = total_moves

    def action_view_linked_moves(self):
        action = self.env['ir.actions.act_window']._for_xml_id('project_milestone_boq.action_picking_tree_all')

        action['display_name'] = _("%(name)s's", name=self.name)

        action['domain'] = [('project_id', '=', self.id)]

        action['context'] = {'default_project_id': self.id}


        return action

    @api.depends("task_ids.product_link_ids")
    def _get_linked_pr(self):
        for rec in self:
            pr_count = self.env['purchase.request'].search_count([('project_id', '=', rec.id)])
            po_count = self.env['purchase.order'].search_count([('project_id', '=', rec.id)])
            rec.linked_pr_count = pr_count
            rec.linked_po_count = po_count

    def action_view_linked_pr(self):
        action = self.env['ir.actions.act_window']._for_xml_id('purchase_request.purchase_request_form_action')

        action['display_name'] = _("%(name)s's Products", name=self.name)

        action['domain'] = [('project_id', '=', self.id)]

        action['context'] = {'default_project_id': self.id}


        return action

    def action_view_linked_po(self):
        action = self.env['ir.actions.act_window']._for_xml_id('purchase.purchase_form_action')

        action['display_name'] = _("%(name)s's Products", name=self.name)

        action['domain'] = [('project_id', '=', self.id)]

        action['context'] = {'default_project_id': self.id}


        return action

    @api.depends('milestone_ids')
    def _compute_milestone_count(self):
        for project in self:
            project.milestone_count = len(project.milestone_ids)

    invoicing_schedular_ids = fields.One2many(
        comodel_name = "project.milestone",
        inverse_name = "project_id",
        string = "Invoicing Schedular"
    )

    def action_view_linked_products(self):
        action = self.env['ir.actions.act_window']._for_xml_id('project_milestone_boq.project_linked_product_action')

        action['display_name'] = _("%(name)s's Products", name=self.name)

        action['domain'] = [('task_id.project_id', '=', self.id)]

        action['context'] = {
            'group_by': ['boq_category_id']
        }

        return action

    product_count = fields.Integer(compute='_compute_product_count', string="Product Count")

    @api.depends('task_ids.product_link_ids')  # Depend on product links of all tasks
    def _compute_product_count(self):
        for project in self:

            product_links = project.task_ids.mapped('product_link_ids')
            project.product_count = len(product_links)

class TaskProductLink(models.Model):
    _name = "task.product.link"
    _description = "Products linked to Tasks (from SO)"

    task_id = fields.Many2one('project.task', string="Task", required=True)
    sale_line_id = fields.Many2one('sale.order.line', string="Sale Order Line")
    sale_order_id = fields.Many2one('sale.order', string="Sale Order")
    product_id = fields.Many2one(comodel_name = 'product.product', string="Product temp")
    milestone_id = fields.Many2one(comodel_name = 'project.milestone', string="Milestone")
    main_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Main Warehouse',
        help='Main warehouse from which stock is transferred to the project warehouse.'
    )
    project_warehouse_id = fields.Many2one('stock.warehouse', string="Project Warehouse")

    available_inventory = fields.Float(
        string="Available Inventory",
        compute="_compute_available_inventory",
        store=False
    )

    def unlink(self):
        raise UserError("You cannot delete Items")
        return super().unlink()


    def action_create_pr(self):
        # self already contains only the selected records
        _logger.info(f"Selected records count: {len(self)}")

        # Filter out records supplied by client
        records_to_process = self.filtered(lambda r: r.supplied_by != 'client')

        if not records_to_process:
            raise UserError(_("No records to process. All selected records are supplied by client."))

        # Collect all lines from selected records
        all_lines = []

        for record in records_to_process:
            _logger.info(
                f"Processing record ID: {record.id}, Product: {record.product_id.name}, supplied_by: {record.supplied_by}")

            # Skip if no product or quantity
            if not record.product_id or record.quantity <= 0:
                continue

            # Create purchase requisition line for this record
            line_vals = {
                'product_id': record.product_id.id,
                'product_qty': record.quantity,
                'product_uom_id': record.product_id.uom_id.id,
                'estimated_cost': record.estimated_cost,
                # 'product_description_variants': record.description or record.product_id.name,
            }

            all_lines.append((0, 0, line_vals))
            _logger.info(f"Added line: {line_vals}")

        if not all_lines:
            raise UserError(_("No valid lines found in selected records. Check if products and quantities are set."))

        # Create single PR with all lines from selected records
        pr_vals = {
            'line_ids': all_lines,
        }

        _logger.info(f"Creating PR with {len(all_lines)} lines from {len(records_to_process)} records")
        _logger.info(f"PR vals: {pr_vals}")

        pr = self.env['purchase.request'].create(pr_vals)

        pr.origin = self.task_id.project_id.reinvoiced_sale_order_id.name
        pr.sale_order_id = self.task_id.project_id.reinvoiced_sale_order_id.id
        pr.project_id = self.task_id.project_id.id
        pr.task_id = self.task_id.id

        # warehouse_id = self.task_id.project_id.warehouse_id

        picking_type_id = self.env['stock.picking.type'].search([('warehouse_id','=',self.project_warehouse_id.id),('code','=','incoming')],limit=1)

        pr.picking_type_id = picking_type_id.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.request',
            'view_mode': 'form',
            'res_id': pr.id,
            'target': 'current',
        }

    def action_create_po(self):

        # Filter records for subcontractor only
        records_to_process = self.filtered(lambda r: r.supplied_by != 'client')
        task_id = records_to_process.mapped('task_id')
        _logger.info(f"taskkkkkkkkk id {task_id}")
        if not records_to_process:
            raise UserError(_("No records to process. All items are supplied by the client"))

        _logger.info(f"Creating PO for {len(records_to_process)} subcontracted records")

        # Get project warehouse location (destination)
        project_warehouse = records_to_process[0].project_warehouse_id if records_to_process[
            0].project_warehouse_id else False
        destination_location_id = project_warehouse.lot_stock_id.id if project_warehouse else False

        picking_type_id = self.env['stock.picking.type'].search([('warehouse_id','=',self.project_warehouse_id.id),('code','=','incoming')],limit=1)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Purchase Order',
            'res_model': 'create.po.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': task_id.id if task_id else False,
                'default_boq_ids': [(6, 0, records_to_process.ids)],
                'default_destination_location_id': destination_location_id,
                'default_picking_type_id': picking_type_id.id,
            },
        }


    @api.depends('product_id')
    def _compute_available_inventory(self):
        for rec in self:
            _logger.info(f"rec {rec}")
            warehouse = rec.task_id.project_id.reinvoiced_sale_order_id.warehouse_id
            product = rec.product_id

            if warehouse and product:
                stock_location = warehouse.lot_stock_id
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', 'child_of', stock_location.id),
                ])
                _logger.info(f"quants {quants}")
                _logger.info(f"quantity {quants.mapped('quantity')}")
                _logger.info(f"reserved_quantity {quants.mapped('reserved_quantity')}")
                rec.available_inventory = sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))
                _logger.info(f"rec.available_inventory{rec.available_inventory}")
            else:
                rec.available_inventory = 99



    description = fields.Text(
        string='Description'
    )

    boq_category_id = fields.Many2one(
        comodel_name="boq.category",
        string="BOQ Category",
    )

    quantity = fields.Float(string="Quantity")

    price_unit = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
        compute='_compute_product_info',
        help="Unit price from the Sales Order line.",
    )
    supplied_by = fields.Selection(
        [
            ('company', 'Company'),
            ('client', 'Client'),
            ('subcontracted', 'Subcontracted'),
            ('purchased', 'Purchased'),
        ],
        string='Supplied By',
        default='purchased',
    )
    sales_subtotal = fields.Monetary(
        string='Sales Subtotal',
        compute='_compute_sales_subtotal',
        currency_field='currency_id',
        store=True
    )

    @api.depends("quantity","price_unit")
    def _compute_sales_subtotal(self):
        for rec in self:
            rec.sales_subtotal = rec.quantity * rec.price_unit

    cost_subtotal = fields.Monetary(
        string='Cost Subtotal',
        compute='_compute_cost_subtotal',
        currency_field='currency_id',
        store=True
    )

    @api.depends("quantity","estimated_cost")
    def _compute_cost_subtotal(self):
        for rec in self:
            rec.cost_subtotal = rec.quantity * rec.estimated_cost

    consumed_qty = fields.Float(
        string='Consumed Qty',
        digits='Product Unit of Measure',
        default=0.0,
        store = True
    )

    estimated_cost = fields.Monetary(
        string='Estimated Cost',
        currency_field='currency_id',
        compute = '_compute_product_info',
        help="Estimated cost per unit",
    )
    

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    @api.depends('sale_order_id.order_line', 'product_id')
    def _compute_product_info(self):
        for rec in self:
            rec.price_unit = 0.0
            rec.supplied_by = False
            rec.estimated_cost = 0.0

            if not rec.product_id:
                continue

            for line in rec.sale_order_id.order_line:
                if line.product_id.id == rec.product_id.id:
                    rec.price_unit = line.price_unit
                    rec.supplied_by = line.x_supplied_by
                    rec.estimated_cost = line.x_estimated_cost
                    break

    is_task_folded = fields.Boolean(compute="_compute_is_task_folded")

    def _compute_is_task_folded(self):
        for rec in self:
            rec.is_task_folded = bool(rec.task_id.stage_id.fold)

    # def action_open_transfer_wizard(self):
    #     # self already contains only the selected records
    #     _logger.info(f"Selected records count: {len(self)}")
    #
    #     # Filter valid records (optional - add your own filter logic if needed)
    #     records_to_process = self.filtered(lambda r: r.product_id and r.quantity > 0)
    #
    #     if not records_to_process:
    #         raise UserError(_("No valid records to process. Please select records with products and quantities."))
    #
    #     # Get the first record's main warehouse (assuming all records share the same context)
    #     first_record = records_to_process[0]
    #
    #     # Collect IDs of selected records
    #     selected_line_ids = records_to_process.ids
    #
    #     action = self.env.ref('project_milestone_boq.create_inventory_transfer_wizard_action').read()[0]
    #     action['context'] = {
    #         'default_warehouse_id': first_record.main_warehouse_id.id,
    #         'default_boq_id': first_record.id,  # Or pass the task/project if needed
    #         'warehouse_id': first_record.main_warehouse_id.id,
    #         'default_boq_line_ids': [(6, 0, selected_line_ids)],  # Pass selected IDs
    #     }
    #
    #     _logger.info(f"Opening transfer wizard for {len(selected_line_ids)} records")
    #
    #     return action

    def action_open_transfer_wizard(self):
        """Open wizard to create inventory transfer from selected BOQ lines"""

        # self already contains only the selected records
        _logger.info(f"Selected records count: {len(self)}")

        # Filter valid records with products and quantities
        records_to_process = self.filtered(lambda r: r.product_id and r.quantity > 0)

        if not records_to_process:
            raise UserError(_("No valid records to process. Please select records with products and quantities."))

        # Validate all records have the same main warehouse
        main_warehouses = records_to_process.mapped('main_warehouse_id')
        if len(main_warehouses) > 1:
            raise UserError(_("All selected records must have the same main warehouse."))

        if not main_warehouses:
            raise UserError(_("Main warehouse is not defined for the selected records."))

        main_warehouse = main_warehouses[0]

        # Validate all records have the same project warehouse
        project_warehouses = records_to_process.mapped('project_warehouse_id')
        if len(project_warehouses) > 1:
            raise UserError(_("All selected records must have the same project warehouse."))

        if not project_warehouses:
            raise UserError(_("Project warehouse is not defined for the selected records."))

        # Collect IDs of selected records
        selected_line_ids = records_to_process.ids

        _logger.info(f"Opening transfer wizard for {len(selected_line_ids)} BOQ lines")

        # Get task or project reference for origin field (optional)
        tasks = records_to_process.mapped('task_id')
        origin_ref = tasks[0].name if len(tasks) == 1 else f"{len(tasks)} Tasks"

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Inventory Transfer'),
            'res_model': 'create.inventory.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_warehouse_id': main_warehouse.id,
                'warehouse_id': main_warehouse.id,
                'default_boq_line_ids': [(6, 0, selected_line_ids)],
                'origin_reference': origin_ref,
            },
        }