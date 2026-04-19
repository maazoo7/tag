# -*- coding: utf-8 -*-

from odoo import http

class IrHttp(http.Controller):
    @http.route(['/odoo'], type='http', auth="user")
    def web_client_debug(self, **kwargs):
        if 'debug' not in kwargs:
            return kwargs
            kwargs['debug'] = '1'
        return http.redirect_with_hash('/odoo?debug=1')