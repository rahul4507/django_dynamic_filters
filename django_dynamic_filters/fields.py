"""
    Custom django ORM fields with filterable configuration support
"""
from django.db import models

class FilterableFieldMixin:
    """
    Mixin that adds filter configuration capabilities to Django model fields.

    This mixin should be applied first in the inheritance chain to ensure
    its __init__ method is called after all other mixins have processed their
    kwargs.
    """
    def __init__(self, *args, **kwargs):
        # Extract filter configuration
        self.filter_config = kwargs.pop('filter_config', {})

        # Call parent constructor
        super().__init__(*args, **kwargs)


class CharField(FilterableFieldMixin, models.CharField):
    """CharField with filter configuration support."""
    pass


class TextField(FilterableFieldMixin, models.TextField):
    """TextField with filter configuration support."""
    pass


class BigIntegerField(FilterableFieldMixin, models.BigIntegerField):
    """BigIntegerField with filter configuration support."""
    pass


class IntegerField(FilterableFieldMixin, models.IntegerField):
    """IntegerField with filter configuration support."""
    pass


class PositiveIntegerField(FilterableFieldMixin, models.PositiveIntegerField):
    """PositiveIntegerField with filter configuration support."""
    pass


class SmallIntegerField(FilterableFieldMixin, models.SmallIntegerField):
    """SmallIntegerField with filter configuration support."""
    pass


class AutoField(FilterableFieldMixin, models.AutoField):
    """AutoField with filter configuration support."""
    pass


class BigAutoField(FilterableFieldMixin, models.BigAutoField):
    """BigAutoField with filter configuration support."""
    pass


class DecimalField(FilterableFieldMixin, models.DecimalField):
    """DecimalField with filter configuration support."""
    pass


class FloatField(FilterableFieldMixin, models.FloatField):
    """FloatField with filter configuration support."""
    pass


class BooleanField(FilterableFieldMixin, models.BooleanField):
    """BooleanField with filter configuration support."""
    pass


class DateField(FilterableFieldMixin, models.DateField):
    """DateField with filter configuration support."""
    pass


class DateTimeField(FilterableFieldMixin, models.DateTimeField):
    """DateTimeField with filter configuration support."""
    pass


class TimeField(FilterableFieldMixin, models.TimeField):
    """TimeField with filter configuration support."""
    pass


class ForeignKey(FilterableFieldMixin, models.ForeignKey):
    """ForeignKey with filter configuration support."""
    pass


class OneToOneField(FilterableFieldMixin, models.OneToOneField):
    """OneToOneField with filter configuration support."""
    pass


class ManyToManyField(FilterableFieldMixin, models.ManyToManyField):
    """ManyToManyField with filter configuration support."""
    pass


class JSONField(FilterableFieldMixin, models.JSONField):
    """JSONField with filter configuration support."""
    pass


class EmailField(FilterableFieldMixin, models.EmailField):
    """EmailField with filter configuration support."""
    pass


class URLField(FilterableFieldMixin, models.URLField):
    """URLField with filter configuration support."""
    pass


class FileField(FilterableFieldMixin, models.FileField):
    """FileField with filter configuration support."""
    pass


class ImageField(FilterableFieldMixin, models.ImageField):
    """ImageField with filter configuration support."""
    pass


class SlugField(FilterableFieldMixin, models.SlugField):
    """SlugField with filter configuration support."""
    pass