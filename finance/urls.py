from django.urls import path
from finance import views

app_name = "finance"

urlpatterns = [
    # Parent
    path("wallet/",                           views.parent_wallet,          name="parent_wallet"),
    path("wallet/topup/",                     views.request_topup,          name="request_topup"),
    path("wallet/pay-fee/",                   views.pay_fee,                name="pay_fee"),
    path("wallet/buy/",                       views.buy_item,               name="buy_item"),
    path("wallet/submit-payment/",            views.submit_payment,         name="submit_payment"),
    path("wallet/pay-hostel/",                   views.parent_pay_hostel,      name="parent_pay_hostel"),
    path("wallet/history/",                   views.transaction_history,    name="transaction_history"),
    path("wallet/balance/",                   views.wallet_balance_api,     name="wallet_balance_api"),
    path("receipt/<int:txn_id>/",             views.receipt_txn,            name="receipt_txn"),
    path("receipt/payment/<int:payment_id>/", views.receipt_payment,        name="receipt_payment"),
    path("invoice/<int:invoice_id>/",         views.view_invoice,           name="view_invoice"),
    # Paystack
    path("paystack/init/",                    views.paystack_init,          name="paystack_init"),
    path("paystack/callback/",                views.paystack_callback,      name="paystack_callback"),
    path("paystack/webhook/",                 views.paystack_webhook,       name="paystack_webhook"),
    # Admin
    path("admin/",                                views.admin_finance_dashboard, name="admin_dashboard"),
    path("admin/payment/<int:payment_id>/review/",views.review_payment,         name="review_payment"),
    path("admin/topup/<int:topup_id>/review/",    views.review_topup,           name="review_topup"),
    path("admin/wallet/",                         views.admin_student_wallet,   name="admin_student_wallet"),
    path("admin/wallet/<int:student_id>/",        views.admin_student_wallet,   name="admin_student_wallet_id"),
    path("admin/wallet/adjust/",                  views.admin_adjust_wallet,    name="admin_adjust_wallet"),
    path("admin/invoices/",                       views.admin_invoices,         name="admin_invoices"),
    path("admin/billing/",                        views.admin_billing_report,   name="admin_billing"),
    path("admin/fees/",                           views.manage_fees,            name="manage_fees"),
    path("admin/fees/waive/",                     views.waive_fee,              name="waive_fee"),
    path("admin/items/",                          views.manage_items,           name="manage_items"),
    path("admin/audit/",                          views.admin_audit_log,        name="admin_audit_log"),
    path("admin/pay-on-behalf/",  views.admin_pay_on_behalf,  name="admin_pay_on_behalf"),
    # Boarder management from wallet page
    path("admin/wallet/<int:student_id>/make-boarder/",   views.make_boarder,   name="make_boarder"),
    path("admin/wallet/<int:student_id>/remove-boarder/", views.remove_boarder, name="remove_boarder"),
    path("admin/wallet/<int:student_id>/pay-hostel/",     views.pay_hostel_fee, name="pay_hostel_fee"),
]