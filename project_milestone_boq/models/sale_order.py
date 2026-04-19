# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
from odoo.exceptions import UserError, AccessError, ValidationError
import re


_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    _description = "sale order ext for project tasks"

    project_id = fields.Many2one('project.project', string="Linked Project")
    linked_pr_count = fields.Integer(compute='_get_linked_pr', string="Linked PR")
    linked_po_count = fields.Integer(compute='_get_linked_po', string="Linked PO")
    moves_count = fields.Integer(compute='_get_related_moves', string="Inventory Moves")


    @api.model
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        # _logger.info(f"create triggred :::: {vals}")

        # vals['warehouse_id'] = False
        # res.warehouse_id = False
        return res
    def write(self, vals):
        # _logger.info(f"write trigger :::: {vals}")
        return super(SaleOrder, self).write(vals)

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

    @api.depends("project_id.task_ids.product_link_ids")
    def _get_linked_pr(self):
        for rec in self:
            if rec.project_id:
                pr_count = self.env['purchase.request'].search_count([('project_id', '=', rec.project_id.id)])
                po_count = self.env['purchase.order'].search_count([('project_id', '=', rec.project_id.id)])
                rec.linked_pr_count = pr_count
                rec.linked_po_count = po_count
            else:
                rec.linked_pr_count = 0
                rec.linked_po_count = 0

    def action_view_linked_pr(self):
        action = self.env['ir.actions.act_window']._for_xml_id('purchase_request.purchase_request_form_action')

        if not self.project_id:
            # force empty result
            action['domain'] = [('id', '=', 0)]
            action['display_name'] = _("No Project Selected")
            return action

        action['display_name'] = _("%(name)s's Products", name=self.name)

        action['domain'] = [('project_id', '=', self.project_id.id)]

        action['context'] = {'default_project_id': self.project_id.id}

        return action

    def action_view_linked_po(self):
        action = self.env['ir.actions.act_window']._for_xml_id('purchase.purchase_form_action')

        if not self.project_id:
            action['domain'] = [('id', '=', 0)]
            action['display_name'] = _("No Project Selected")
            return action

        action['display_name'] = _("%(name)s's Products", name=self.name)

        action['domain'] = [('project_id', '=', self.project_id.id)]

        action['context'] = {'default_project_id': self.project_id.id}

        return action

    def action_confirm(self):
        # res = super(SaleOrder, self).action_confirm()
        for order in self:
            order_status = order.create_project_and_linked_records()
        return super(SaleOrder, self).action_confirm()


    def action_view_project(self):
        """Open the project configuration page"""
        self.ensure_one()
        if not self.project_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': 'Project',
            'res_model': 'project.project',
            'view_mode': 'form',
            'res_id': self.project_id.id,
            'target': 'current',
        }



    # def write(self, vals):
    #     res = super(SaleOrder, self).write(vals)
    #     _logger.info(f"tasksss======{vals}")
    #     return res
    #
    # @api.model
    # def create(self, vals):
    #     res = super(SaleOrder, self).create(vals)
    #     _logger.info(f"tasksss create======{vals}")
    #     return res

    milestone_count = fields.Integer(
        string='Milestone Count',
        compute='_compute_milestone_count',
        store=True
    )

    @api.depends('project_id.milestone_ids')
    def _compute_milestone_count(self):
        for order in self:
            if order.project_id:
                milestones = self.env['project.milestone'].search([
                    '|',
                    ('sale_order_id', '=', order.id),
                    ('project_id', '=', order.project_id.id)
                ])
                order.milestone_count = len(milestones)
            else:
                order.milestone_count = 0

    def action_view_linked_milestones(self):
        self.ensure_one()
        milestones = self.env['project.milestone'].search([
            '|',
            ('sale_order_id', '=', self.id),
            ('project_id', '=', self.project_id.id)
        ])

        return {
            'type': 'ir.actions.act_window',
            'name': 'Milestones',
            'res_model': 'project.milestone',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('project_milestone_boq.view_project_milestone_list_view').id, 'list'),
                (self.env.ref('project_milestone_boq.view_project_milestone_form').id, 'form')
            ],
            'domain': [('id', 'in', milestones.ids)],
            'context': {
                'default_project_id': self.project_id.id,
                'default_sale_order_id': self.id,
            }
        }

    def create_project_and_linked_records(self):
        """Create a project, milestones, and tasks based on sections/subsections."""
        self.ensure_one()

        Project = self.env['project.project']
        Milestone = self.env['project.milestone']
        Task = self.env['project.task']
        project_wh = False
        # 🔹 Create or reuse project
        project = self.project_id
        main_warehouse_id = self.warehouse_id
        if not project:
            template = self.env['project.project'].search([
                ('name', '=', 'Project Template')
            ], limit=1)
            project_vals = {
                'name': f"{self.name} - Project",
                'partner_id': self.partner_id.id,
                'allow_milestones': True,
                'allow_billable': True,
                'reinvoiced_sale_order_id': self.id,
            }
            if template and template.type_ids:
                project_vals['type_ids'] = [(6, 0, template.type_ids.ids)]
            project = Project.create(project_vals)
            self.project_id = project
            warehouse_code = re.sub(r'[^A-Za-z0-9]', '', self.name[:3].upper())
            project_wh = self.env['stock.warehouse'].create({
                'name': f"{self.name} Warehouse",
                'code': f"{warehouse_code}{self.id}",
                'company_id': self.company_id.id,
            })
            self.warehouse_id = project_wh.id
            _logger.info(f"✅ Created Project Warehouse: {project_wh.name}")

            main_wh = self.env['stock.warehouse'].search(
                [('company_id', '=', self.company_id.id)],
                limit=1
            )
            if not main_wh:
                raise UserError("Main warehouse not found!")
            product_lines = self.order_line.filtered(lambda l: l.product_id.type == 'consu' and l.product_uom_qty > 0)
            # if product_lines:
            #     picking_type = main_wh.int_type_id
            #     _logger.info(f"main warehouse picking type {picking_type}")
            #     picking = self.env['stock.picking'].create({
            #         'picking_type_id': picking_type.id,
            #         'location_id': main_wh.lot_stock_id.id,
            #         'location_dest_id': project_wh.lot_stock_id.id,
            #         'origin': self.name,
            #     })
            #
            #     for line in self.order_line.filtered(lambda l: l.product_id.type == 'consu' and l.product_uom_qty > 0):
            #         move = self.env['stock.move'].create({
            #             'product_id': line.product_id.id,
            #             'product_uom': line.product_uom_id.id,
            #             'product_uom_qty': line.product_uom_qty,
            #             'picking_id': picking.id,
            #             'location_id': main_wh.lot_stock_id.id,
            #             'location_dest_id': project_wh.lot_stock_id.id,
            #         })
            #         _logger.info(f"Created move {move.id} for {line.product_id.display_name}")
            #
            #     # Now confirm and process once
            #     _logger.info(f"Before confirm picking state: {picking.state}")
            #     picking.action_confirm()
            #     picking.action_assign()
            #
            # # Mark quantities done
            #     for move_line in picking.move_line_ids:
            #         move_line.qty_done = move_line.move_id.product_uom_qty or 1.0
            #
            #     # Validate transfer
            #     picking.with_context(skip_immediate=True).button_validate()
            #
            #     _logger.info(f"✅ Stock transferred {main_wh.name} → {project_wh.name} for {self.name}")
        current_milestone = False
        current_task = False

        # 🔹 Iterate over sale order lines
        for line in self.order_line:
            _logger.info(f"current section {line.display_type}")
            if line.display_type == 'line_section':
                # Create milestone for section
                current_milestone = Milestone.create({
                    'name': line.name,
                    'project_id': project.id,
                    'sale_order_id': self.id,
                    # 'sale_line_id': line.id,
                })
                _logger.info(f"current milestone {current_milestone}")
            # if not current_milestone:
            #     raise UserError(_(
            #         f"Cannot create task '{line.name}' without a milestone. "
            #         f"Please add a section (milestone) before subsections (tasks)."
            #     ))
            elif current_milestone and line.display_type == 'line_subsection':

                _logger.info(f"line_subsection : {current_milestone},=={line.display_type}")
                # Create task for subsection
                current_task = Task.sudo().create({
                    'name': line.name,
                    'project_id': project.id,
                    'milestone_id': current_milestone.id,
                    'partner_id': self.partner_id.id,
                    # 'allow_billable' : True,
                    # 'sale_line_id': line.id,
                })
            #
            # if not current_task:
            #     raise UserError(_(
            #         f"Cannot create BOQ item for product '{line.product_id.name}' without a task. "
            #         f"Please add a subsection (task) before adding products."
            #     ))
            elif current_task and not line.display_type and line.product_id:
                self.env['task.product.link'].create({
                    'task_id': current_task.id,
                    'sale_line_id': line.id,
                    'milestone_id': current_milestone.id,
                    'sale_order_id': self.id,
                    'product_id': line.product_id.id,
                    'quantity': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'supplied_by': line.x_supplied_by,
                    'boq_category_id': line.product_id.boq_category_id.id,
                    'main_warehouse_id' : main_warehouse_id.id,
                    'project_warehouse_id' : project_wh.id
                })
        return True

class SaleOrderLineExt(models.Model):
    _inherit = 'sale.order.line'
    _description = 'Sale order Ext'

    x_supplied_by = fields.Selection(
        [
            ('company', 'Company'),
            ('client', 'Client'),
            ('subcontracted', 'Subcontracted'),
            ('purchased', 'Purchased'),
        ],
        string='Supplied By',
        default='company'
    )
    x_estimated_cost = fields.Float(string="Cost")

    @api.onchange('x_supplied_by')
    def check_unit_price(self):
        for rec in self:
            _logger.info(f"test {rec.x_supplied_by}")
            if rec.x_supplied_by == "client":
                rec.price_unit = 0.0
