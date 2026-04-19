{
    'name': 'Construction Management - Sales to Invoice',
    'version': '19.0.1.0.0',
    'category': 'Sales/Project',
    'summary': 'Custom management for construction company with milestone-based invoicing',
    'description': """
        Construction Company Management Module
        =======================================
        * Sales Order sections as Milestones
        * Sales Order subsections as Tasks
        * BOQ (Bill of Quantities) management
        * Supplied by field (Company/Client)
        * Milestone-based invoicing
        * Automatic delivery order updates
        * Project invoicing schedule
    """,
    'author': 'Team GalaxyITC',
    'website': 'https://www.galaxyitc.com',
    'depends': [
        'base',
        'product',
        'sale',
        'stock',
        'project',
        'sale_project',
        'purchase',
        'fleet',
        'purchase_request',
        'purchase_requisition',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/product.xml',
        'views/project.xml',
        'views/warehouse.xml',
        'views/purchase.xml',
        'data/project_template.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         # 'project_milestone_boq/static/src/scss/**/*',
    #         'project_milestone_boq/static/src/js/**/*',
    #         # 'project_milestone_boq/static/src/xml/**/*',
    #     ],
    # },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}