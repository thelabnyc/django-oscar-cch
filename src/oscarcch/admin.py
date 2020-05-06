from django.contrib import admin
from oscar.core.loading import get_model

OrderTaxation = get_model('cch', 'OrderTaxation')
LineItemTaxationDetail = get_model('cch', 'LineItemTaxationDetail')
LineItemTaxation = get_model('cch', 'LineItemTaxation')
ShippingTaxationDetail = get_model('cch', 'ShippingTaxationDetail')
ShippingTaxation = get_model('cch', 'ShippingTaxation')


@admin.register(OrderTaxation)
class OrderTaxationAdmin(admin.ModelAdmin):
    list_filter = ['transaction_status']
    search_fields = ['transaction_id', 'messages']

    fields = ['order', 'transaction_id', 'transaction_status', 'total_tax_applied', 'messages']
    list_display = fields
    readonly_fields = fields


class LineItemTaxationDetailInline(admin.StackedInline):
    model = LineItemTaxationDetail
    readonly_fields = ['data']


@admin.register(LineItemTaxation)
class LineItemTaxationAdmin(admin.ModelAdmin):
    list_filter = ['country_code', 'state_code']

    fields = ['line_item', 'country_code', 'state_code', 'total_tax_applied']
    list_display = fields
    readonly_fields = fields
    inlines = [
        LineItemTaxationDetailInline
    ]


class ShippingTaxationDetailInline(admin.StackedInline):
    model = ShippingTaxationDetail
    readonly_fields = ['data']


@admin.register(ShippingTaxation)
class ShippingTaxationAdmin(admin.ModelAdmin):
    list_filter = ['country_code', 'state_code']

    fields = ['order', 'country_code', 'state_code', 'total_tax_applied']
    list_display = fields
    readonly_fields = fields
    inlines = [
        ShippingTaxationDetailInline,
    ]
