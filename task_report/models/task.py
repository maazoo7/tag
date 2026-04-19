from odoo import api, models, fields
import json

import logging

_logger = logging.getLogger(__name__)


class ProjectUpdate(models.Model):
    _inherit = "project.update"

    task_id = fields.Many2one(
        "project.task",
        string="Task",
        help="Task this update is related to"
    )


class Task(models.Model):
    _inherit = "project.task"

    update_ids = fields.One2many(
        "project.update",
        "task_id",
        string="Task Updates"
    )

    update_count = fields.Integer(
        string="Update Count",
        compute="_compute_update_count"
    )

    @api.depends('update_ids')
    def _compute_update_count(self):
        for task in self:
            task.update_count = len(task.update_ids)

    def action_view_task_updates(self):
        self.ensure_one()
        context = {
            "default_task_id": self.id,
        }
        # Only add project_id to context if it exists
        if self.project_id:
            context["default_project_id"] = self.project_id.id
            context["active_id"] = self.project_id.id

        return {
            "type": "ir.actions.act_window",
            "name": "Task Updates",
            "res_model": "project.update",
            "view_mode": "list,form",
            "domain": [("task_id", "=", self.id)],
            "context": context,
        }