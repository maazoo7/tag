{
    'name': 'Purchase Request Lines',
    'version': '19.0.1.0.0',
    'category': 'Project',
    'summary': 'Purchase Request Lines',
    'description': """
       Purchase Request Lines
    """,
    'author': 'Team GalaxyITC',
    'website': 'https://www.galaxyitc.com',
    'depends': [
       'base', 'purchase_request','purchase'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_order.xml'
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}