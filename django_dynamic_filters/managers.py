"""
Custom managers and QuerySets with dynamic filtering support
"""

import datetime
from django.db import models
from django.db.models.signals import pre_delete, post_delete

from .filters import ModelFilter


def get_current_request():
    """
    Get the current request from thread local storage.
    This is meant to be replaced with actual middleware in production.
    """
    try:
        from threading import local
        _thread_locals = local()
        return getattr(_thread_locals, 'request', None)
    except ImportError:
        return None


class DynamicFilterQuerySet(models.QuerySet):
    """
    Custom QuerySet with filtering capabilities
    """

    def apply_filtering(self, request_data=None, filter_config=None):
        """
        Apply filtering to the queryset

        This handles both model fields and annotated fields in the queryset
        """
        # Use provided request data or get from current request
        data = request_data or (get_current_request() and get_current_request().GET or {})

        return ModelFilter(
            model=self.model,
            request_data=data,
            queryset=self,
            config=filter_config or {}
        ).qs


class DynamicFilterManager(models.Manager):
    """
    Manager with dynamic filtering capabilities.
    """

    def __init__(self):
        super().__init__()
        self._queryset_class = DynamicFilterQuerySet

    def get_queryset(self) -> DynamicFilterQuerySet:
        return self._queryset_class(self.model, using=self._db)

    def apply_filtering(self, request_data=None, filter_config=None):
        """
        Apply filtering to the base queryset with request data
        """
        return self.get_queryset().apply_filtering(
            request_data=request_data,
            filter_config=filter_config
        )


class SoftDeleteQuerySet(DynamicFilterQuerySet):
    """
    QuerySet that implements soft delete functionality
    """

    def delete(self):
        """
        Soft Delete Operation
        """
        for obj in self:
            obj.delete()


class SoftDeleteManager(DynamicFilterManager):
    """
    Manager for soft-deletion. Excludes rows where is_deleted=True.
    """

    def __init__(self):
        super().__init__()
        self._queryset_class = SoftDeleteQuerySet

    def get_queryset(self):
        # Exclude softly deleted rows by default
        return super().get_queryset().exclude(is_deleted=True)

    def all_with_deleted(self):
        # Return all records, including soft-deleted
        return super().get_queryset()

    def only_deleted(self):
        # Return only soft-deleted records
        return super().get_queryset().filter(is_deleted=True)