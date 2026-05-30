"""
tenants/context_processors.py
Injects tenant and plan info into every template context.
"""

def tenant_context(request):
    tenant = getattr(request, 'tenant', None)
    return {
        'tenant':       tenant,
        'tenant_plan':  tenant.plan if tenant else None,
        'is_on_trial':  tenant.is_on_trial if tenant else False,
        'trial_days':   tenant.days_until_trial_ends() if tenant else None,
    }
