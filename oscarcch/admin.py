from django.contrib import admin

from .models import (
    LineItemTaxation,
    LineItemTaxationDetail,
    OrderTaxation,
    ShippingTaxation,
    ShippingTaxationDetail,
)


@admin.register(OrderTaxation)
class OrderTaxationAdmin(admin.ModelAdmin[OrderTaxation]):
    list_filter = ["transaction_status"]
    search_fields = ["transaction_id", "messages"]

    fields = [
        "order",
        "transaction_id",
        "transaction_status",
        "total_tax_applied",
        "messages",
    ]
    list_display = [
        "order",
        "transaction_id",
        "transaction_status",
        "total_tax_applied",
        "messages",
    ]
    readonly_fields = [
        "order",
        "transaction_id",
        "transaction_status",
        "total_tax_applied",
        "messages",
    ]


class LineItemTaxationDetailInline(
    admin.StackedInline[LineItemTaxationDetail, LineItemTaxation]
):
    model = LineItemTaxationDetail
    readonly_fields = ["data"]


@admin.register(LineItemTaxation)
class LineItemTaxationAdmin(admin.ModelAdmin[LineItemTaxation]):
    list_filter = ["country_code", "state_code"]

    fields = ["line_item", "country_code", "state_code", "total_tax_applied"]
    list_display = ["line_item", "country_code", "state_code", "total_tax_applied"]
    readonly_fields = ["line_item", "country_code", "state_code", "total_tax_applied"]
    inlines = [LineItemTaxationDetailInline]


class ShippingTaxationDetailInline(
    admin.StackedInline[ShippingTaxationDetail, ShippingTaxation]
):
    model = ShippingTaxationDetail
    readonly_fields = ["data"]


@admin.register(ShippingTaxation)
class ShippingTaxationAdmin(admin.ModelAdmin[ShippingTaxation]):
    list_filter = ["country_code", "state_code"]

    fields = ["order", "country_code", "state_code", "total_tax_applied"]
    list_display = ["order", "country_code", "state_code", "total_tax_applied"]
    readonly_fields = ["order", "country_code", "state_code", "total_tax_applied"]
    inlines = [
        ShippingTaxationDetailInline,
    ]
