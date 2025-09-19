from rest_framework.throttling import ScopedRateThrottle


class InvoiceExportThrottle(ScopedRateThrottle):
    scope = "invoice.export"

