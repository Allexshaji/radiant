"""Names of every massage package page. Kept apart from urls.py so accounts.access can read it
without importing the views (which import accounts.access)."""
PACKAGE_PAGES = [
    "package_dashboard", "customer_list", "customer_add", "customer_detail", "customer_edit",
    "customer_package_add", "package_list", "package_add", "package_detail", "package_edit",
    "package_delete", "package_renew", "package_visit_add", "package_visit_undo", "package_visit_delete",
    "package_follow_up", "package_alerts", "package_mark_called", "package_follow_ups", "package_renewals", "package_rates",
]
