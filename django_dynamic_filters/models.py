"""
Base models with filtering capabilities
"""

import datetime
from django.db import models
from django.db.models.signals import pre_delete, post_delete

from .managers import DynamicFilterManager, SoftDeleteManager


class FilterableModel(models.Model):
    """
    Base model with dynamic filtering support
    """
    objects = DynamicFilterManager()

    class Meta:
        abstract = True


class TimestampedModel(FilterableModel):
    """
    Abstract model with created/modified timestamps
    """
    created_date = models.DateTimeField(auto_now_add=True)
    last_modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(TimestampedModel):
    """
    Abstract model with soft-delete behavior.
    """
    objects = SoftDeleteManager()

    # Soft-delete fields
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        # Soft-delete: mark and timestamp
        pre_delete.send(self.__class__, instance=self)
        self.is_deleted = True
        self.deleted_at = datetime.datetime.now()
        self.save()
        post_delete.send(self.__class__, instance=self)