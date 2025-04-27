from django.db import models
from django_dynamic_filters.models import SoftDeleteModel
from django_dynamic_filters.fields import (
    CharField, DateTimeField, BooleanField, DecimalField
)


class Category(SoftDeleteModel):
    name = CharField(
        max_length=100,
        filter_config={
            'searchable': True,
            'lookups': ['exact', 'icontains'],
        }
    )


class Product(SoftDeleteModel):
    name = CharField(
        max_length=100,
        filter_config={
            'searchable': True,
        }
    )
    description = CharField(
        max_length=255,
        blank=True,
        null=True,
        filter_config={
            'searchable': True,
        }
    )
    price = DecimalField(
        max_digits=10,
        decimal_places=2,
        filter_config={
            'lookups': ['exact', 'gt', 'lt', 'range'],
        }
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE
    )
    created_at = DateTimeField(
        auto_now_add=True,
        filter_config={
            'range_filter': True,
        }
    )
    is_active = BooleanField(
        default=True,
        filter_config={
            'lookups': ['exact'],
        }
    )