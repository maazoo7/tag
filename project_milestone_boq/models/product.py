# -*- coding: utf-8 -*-

from odoo import api,models,fields


class ProductTemplateExt(models.Model):
    _inherit = "product.template"
    _description = "Addition for project to task flow"

    boq_category = fields.Selection([('test1','Test1'),('test2','Test2'),('test3','Test3')], string="BOQ Category TEST")
    boq_category_id = fields.Many2one(
        comodel_name = "boq.category",
        string = "BOQ Category",
        domain="[('product_type', '=', type)]"
    )


class ProductBoqcategory(models.Model):
    _name = "boq.category"
    _description = "BOQ Categories for product"

    name = fields.Char(string="Name")
    product_type = fields.Selection([
        ('consu', 'Goods'),
        ('service', 'Service'),
        ('combo', 'Combo'),
    ], string="Product Type", default='consu')

class SaleOrderTemplateLine(models.Model):
    _inherit = 'sale.order.template.line'

    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_subsection', "Subsection"),
            ('line_note', "Note"),
        ],
        default=False)