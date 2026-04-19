{
    'name': 'Rejection Wizard for PO',
    'version': '19.0.1.0.0',
    'category': 'Purchase',
    'summary': 'wizard for rejecting po',
    'description': """
       PO Rejecting wizard
    """,
    'author': 'Team GalaxyITC',
    'website': 'https://www.galaxyitc.com',
    'depends': [
       'project_milestone_boq', 'purchase_request'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/rejection_wizard.xml'
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}