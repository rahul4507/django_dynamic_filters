"""
Dynamic Filter Module for Django ORM with Meta-based configuration and multi-value parameter support

This module provides flexible filtering capabilities for Django models with
filter configuration defined in the model's Meta class.
"""

import inspect
import datetime
import logging
import json
from urllib import parse

from typing import Dict, List, Any, Type, Optional

from django.db.models import Q, DateField, DateTimeField, Field, Model, JSONField
from django.db.models.constants import LOOKUP_SEP
from django.db.models.functions import Concat
from django.http import QueryDict
from utils.constants import SEARCH_PARAM, ORDERING_PARAM, DEFAULT_ORDERING, ADVANCED_FILTER_PARAM, \
    DATE_RANGE_SUFFIXES



class FieldTypeRegistry:
    """Registry of field types and their default lookup expressions"""

    # Default lookup mappings for field types
    DEFAULT_LOOKUPS = {
        'text': 'icontains',
        'integer': 'exact',
        'decimal': 'exact',
        'boolean': 'exact',
        'date': 'exact',
        'datetime': 'exact',
        'enum': 'exact',
        'relation': 'exact',
        'array': 'contains',
        'json': 'has_key',
    }

    # Mapping of Django internal types to our simplified types
    DJANGO_TYPE_MAPPING = {
        'CharField': 'text',
        'TextField': 'text',
        'SlugField': 'text',
        'EmailField': 'text',
        'URLField': 'text',
        'FileField': 'text',
        'FilePathField': 'text',
        'IntegerField': 'integer',
        'PositiveIntegerField': 'integer',
        'SmallIntegerField': 'integer',
        'BigIntegerField': 'integer',
        'AutoField': 'integer',
        'BigAutoField': 'integer',
        'FloatField': 'decimal',
        'DecimalField': 'decimal',
        'BooleanField': 'boolean',
        'NullBooleanField': 'boolean',
        'DateField': 'date',
        'DateTimeField': 'datetime',
        'TimeField': 'text',
        'ForeignKey': 'relation',
        'OneToOneField': 'relation',
        'ManyToManyField': 'relation',
        'JSONField': 'json',
        'ArrayField': 'array',
    }

    # Default searchable field types
    SEARCHABLE_TYPES = {'text', 'enum'}

    # Default lookup expressions by field type
    DEFAULT_LOOKUPS_BY_TYPE = {
        'text': ['exact', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith'],
        'integer': ['exact', 'gt', 'gte', 'lt', 'lte', 'in', 'range'],
        'decimal': ['exact', 'gt', 'gte', 'lt', 'lte', 'range'],
        'boolean': ['exact'],
        'date': ['exact', 'gt', 'gte', 'lt', 'lte', 'range'],
        'datetime': ['exact', 'gt', 'gte', 'lt', 'lte', 'range', 'date'],
        'enum': ['exact', 'in'],
        'relation': ['exact', 'in'],
        'json': ['has_key', 'contains', 'contained_by'],
        'array': ['contains', 'contained_by', 'overlap', 'len']
    }

    # Lookup types that expect multiple values
    MULTI_VALUE_LOOKUPS = ['in', 'range']

    @classmethod
    def get_field_type(cls, field: Field) -> str:
        """Determine the simplified type of a Django field"""
        if cls._is_choice_field(field):
            return 'enum'

        if isinstance(field, DateField) and not isinstance(field, DateTimeField):
            return 'date'

        if isinstance(field, DateTimeField):
            return 'datetime'

        if isinstance(field, JSONField):
            return 'json'

        if hasattr(field, 'get_internal_type'):
            django_type = field.get_internal_type()
            return cls.DJANGO_TYPE_MAPPING.get(django_type, 'text')

        return 'text'  # Default to text for unknown types

    @classmethod
    def _is_choice_field(cls, field: Field) -> bool:
        """Check if a field is a choice/enum field"""
        # Check for BaseChoice-derived fields
        if hasattr(field, '_choices_cls'):
            return True

        # Check class hierarchy
        class_hierarchy = inspect.getmro(field.__class__)
        for base_cls in class_hierarchy:
            if 'BaseChoiceField' in base_cls.__name__ or 'ChoiceField' in base_cls.__name__:
                return True

        # Check if field has conventional choices
        return hasattr(field, 'choices') and bool(field.choices)

    @classmethod
    def get_default_lookup(cls, field_type: str) -> str:
        """Get the default lookup expression for a field type"""
        return cls.DEFAULT_LOOKUPS.get(field_type, 'exact')

    @classmethod
    def get_lookups_for_type(cls, field_type: str) -> List[str]:
        """Get the available lookup expressions for a field type"""
        return cls.DEFAULT_LOOKUPS_BY_TYPE.get(field_type, ['exact'])


class ModelFilter:
    """
    A flexible filter class that uses Django's ORM to apply filters and ordering
    based on request parameters with Meta class configuration.

    Key features:
    - Filter configuration via model's Meta class
    - Advanced filtering via GET parameters
    - Date range filtering with _min and _max suffixes
    - Text search across searchable fields
    - Filtering on related model fields
    - Custom ordering with comma-separated fields
    - Filter persistence via SavedFilter model
    - Support for multi-value parameters (e.g., ?field=1&field=2)

    Usage:
        # Basic usage with request parameters
        filter = ModelFilter(Consumer, request.GET)
        filtered_queryset = filter.apply().qs

        # With a pre-filtered queryset
        filter = ModelFilter(
            Consumer,
            request.GET,
            queryset=Consumer.objects.filter(is_active=True)
        )
        filtered_queryset = filter.apply().qs

        # With advanced filter via GET parameter
        # GET /consumers/?filter={"operator":"AND","conditions":[{"field":"status","lookup":"exact","value":1},{"field":"is_vip","lookup":"exact","value":true}]}
        filter = ModelFilter(Consumer, request.GET)
        filtered_queryset = filter.apply().qs
    """

    def __init__(
            self,
            model: Type[Model],
            request_data: Dict = None,
            queryset=None,
            config: Dict = None
    ):
        """
        Initialize the filter with a model, request data, and optional queryset.

        Args:
            model: The Django model class to filter
            request_data: Dict-like object containing filter parameters (e.g. request.GET)
            queryset: Optional pre-filtered queryset. If None, model.objects.all() will be used
            config: Optional filter configuration to override model-defined config
        """
        self.model = model
        self.request_data = request_data or {}
        self.base_queryset = queryset or model.objects.all()
        self.filtered_queryset = None
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.config = config or {}

        # Initialize field registry
        self.field_registry = {}
        self._analyze_model_fields()

        # Register annotated fields by inspecting queryset annotations
        self._register_annotated_fields()

    def _register_annotated_fields(self):
        """
        Register fields that are annotated in the queryset
        """
        # Django stores annotations in query.annotations dictionary
        if hasattr(self.base_queryset, 'query') and hasattr(self.base_queryset.query, 'annotations'):
            for field_name, expression in self.base_queryset.query.annotations.items():
                # Skip complex expressions we can't easily categorize
                field_type = self._determine_annotation_type(expression)
                if field_type:
                    self._register_annotated_field(field_name, field_type)

    def _determine_annotation_type(self, expression):
        """
        Determine the type of an annotated field based on its expression
        """
        # Handle common annotation types
        if isinstance(expression, Concat):
            return 'text'

        # Add more type detection logic as needed
        # For example, checking for Sum, Count, etc.

        return 'text'  # Default to text if we can't determine

    def _register_annotated_field(self, field_name, field_type):
        """
        Register an annotated field for filtering
        """
        # Skip if already registered or in exclusion list
        if field_name in self.field_registry:
            return

        # Get lookups based on field type
        lookups = FieldTypeRegistry.get_lookups_for_type(field_type)

        # Get default lookup for field type
        default_lookup = FieldTypeRegistry.get_default_lookup(field_type)
        filterable = True
        searchable = True
        allowed_fields_for_filter = set(self.config.get('filter_fields', []))
        if allowed_fields_for_filter and field_name not in allowed_fields_for_filter:
            filterable = False

        allowed_fields_for_search = set(self.config.get('search_fields', []))
        if allowed_fields_for_search and field_name not in allowed_fields_for_search:
            searchable = False

        # Build field metadata
        field_info = {
            'field_path': field_name,  # Annotated fields use their name directly
            'field': None,  # No actual field object for annotated fields
            'type': field_type,
            'searchable': searchable,
            'filterable': filterable,
            'lookups': lookups,
            'default_lookup': default_lookup,
            'is_annotated': True,
            'range_filter': False,
            'enum_class': None,
        }

        self.field_registry[field_name] = field_info

    def _analyze_model_fields(self) -> None:
        """
        Analyze model fields to determine their types and filter properties,
        including fields from related models
        """
        # Register fields from the model itself
        for field in self.model._meta.get_fields():
            self._register_field(field)
        # Process fields from related models (up to one level deep)
        for field in self.model._meta.get_fields():
            self._register_field(field)
            if field.is_relation and hasattr(field, 'related_model'):
                related_model = field.related_model
                relation_name = field.name

                for rel_field in related_model._meta.get_fields():
                    if hasattr(rel_field, 'get_internal_type'):
                        self._register_field(rel_field, relation_name)

    def _register_field(self, field: Field, relation_prefix: str = None) -> None:
        """Register a field in the field registry"""
        # Skip auto-created reverse relations we don't need
        if field.auto_created and not field.concrete:
            return

        field_name = field.name
        field_path = field_name
        if relation_prefix:
            field_path = f"{relation_prefix}{LOOKUP_SEP}{field_name}"
            if field_name in self.field_registry:
                field_name = f"{relation_prefix}_{field_name}"

        # Skip if already registered
        if field_name in self.field_registry:
            return

        field_type = FieldTypeRegistry.get_field_type(field)

        # Check for field-level filter configuration
        field_config = {}
        if hasattr(field, 'filter_config'):
            field_config = field.filter_config

        # Determine if field is searchable
        searchable = field_config.get('searchable', False)
        filterable = True
        allowed_fields_for_filter = set(self.config.get('filter_fields', []))
        if allowed_fields_for_filter and field_name not in allowed_fields_for_filter:
            filterable = False

        allowed_fields_for_search = set(self.config.get('search_fields', []))
        if allowed_fields_for_search and field_name not in allowed_fields_for_search:
            searchable = False

        # Get available lookups
        lookups = field_config.get('lookups')
        if lookups is None:
            lookups = FieldTypeRegistry.get_lookups_for_type(field_type)

        # Get default lookup
        default_lookup = field_config.get('default')
        if default_lookup is None:
            default_lookup = FieldTypeRegistry.get_default_lookup(field_type)

        # Check if field supports range filtering
        range_filter = field_config.get('range_filter')
        if range_filter is None:
            range_filter = field_type in ('date', 'datetime', 'integer', 'decimal')

        # Build field metadata
        field_info = {
            'field_path': field_path,
            'field': field,
            'type': field_type,
            'searchable': searchable,
            'filterable': filterable,
            'lookups': lookups,
            'default_lookup': default_lookup,
            'range_filter': range_filter,
            'enum_class': self._get_enum_class(field) if field_type == 'enum' else None,
        }

        self.field_registry[field_name] = field_info

    def _get_enum_class(self, field: Field) -> Optional[Type]:
        """Extract the enum class from a choice field"""
        if hasattr(field, '_choices_cls'):
            return field._choices_cls

        if hasattr(field, 'choices') and field.choices:
            try:
                first_choice = field.choices[0]
                if isinstance(first_choice, tuple) and len(first_choice) > 0:
                    choice_value = first_choice[0]
                    if hasattr(choice_value, '__class__'):
                        return choice_value.__class__
            except (IndexError, AttributeError):
                pass

        return None

    def _get_field_values(self, field_name: str) -> Any:
        """
        Get values for a field from request data, handling multiple values correctly

        Args:
            field_name: Name of the field

        Returns:
            Single value or list of values depending on the request data
        """
        # Check if we're working with a QueryDict (from request.GET/POST)
        if isinstance(self.request_data, QueryDict):
            # getlist returns all values for a parameter
            values = self.request_data.getlist(field_name)
            if len(values) > 1:
                return values
            elif len(values) == 1:
                return values[0]
            return None
        else:
            # Regular dict behavior
            return self.request_data.get(field_name)

    def _build_field_filter(self, field_name: str, value: Any = None, lookup: str = None) -> Optional[Q]:
        """
        Build Q object for a field filter
        """
        if field_name not in self.field_registry:
            return None

        field_info = self.field_registry[field_name]

        if not field_info["filterable"]:
            return None

        # Get value if not provided
        if value is None:
            value = self._get_field_values(field_name)
            if value is None:
                return None

        # Handle lookup selection
        lookup = lookup or field_info['default_lookup']
        if lookup not in field_info['lookups']:
            self.logger.warning(
                f"Lookup '{lookup}' not allowed for field '{field_name}'. Using default: {field_info['default_lookup']}"
            )
            lookup = field_info['default_lookup']

        # Handle null values
        if value is None or value == '':
            return Q(**{f"{field_info['field_path']}__isnull": True})

        # Process 'in' lookup values
        if lookup == 'in' and not isinstance(value, (list, tuple)):
            value = value.split(',') if isinstance(value, str) and ',' in value else [value]

        # Convert value based on field type
        value = self._convert_value_by_type(value, field_info)

        # Build and return Q object
        return Q(**{f"{field_info['field_path']}__{lookup}": value})

    def _convert_value_by_type(self, value, field_info):
        """Helper method to convert values based on field type"""
        type_handlers = {
            'boolean': self._convert_to_boolean,
            'integer': self._convert_to_integer,
            'decimal': self._convert_to_decimal
        }

        field_type = field_info['type']

        # Handle basic types
        if field_type in type_handlers:
            converter = type_handlers[field_type]
            return [converter(v) for v in value] if isinstance(value, (list, tuple)) else converter(value)

        return value

    def _convert_to_boolean(self, value: Any) -> bool:
        """Convert a value to boolean"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 't', 'yes', 'y', '1')
        return bool(value)

    def _convert_to_integer(self, value: Any) -> int:
        """Convert a value to integer"""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def _convert_to_decimal(self, value: Any) -> float:
        """Convert a value to decimal/float"""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _build_date_range_filter(self, field_name: str) -> Optional[Q]:
        """Build Q object for date range filter"""
        if field_name not in self.field_registry:
            return None

        field_info = self.field_registry[field_name]

        if not field_info["filterable"]:
            return None

        min_param = f"{field_info['field_path']}_min"
        max_param = f"{field_info['field_path']}_max"

        q_obj = None

        # Get min value if present
        if min_param in self.request_data and self.request_data[min_param]:
            min_value = self._parse_date(self.request_data[min_param])
            if min_value:
                q_obj = Q(**{f"{field_info['field_path']}__gte": min_value})

        # Get max value if present
        if max_param in self.request_data and self.request_data[max_param]:
            max_value = self._parse_date(self.request_data[max_param])
            if max_value:
                max_q = Q(**{f"{field_info['field_path']}__lte": max_value})
                q_obj = max_q if q_obj is None else q_obj & max_q

        return q_obj

    def _build_datetime_range_filter(self, field_name: str) -> Optional[Q]:
        """Build Q object for datetime range filter"""
        if field_name not in self.field_registry:
            return None

        field_info = self.field_registry[field_name]

        if not field_info["filterable"]:
            return None

        min_param = f"{field_info['field_path']}_min"
        max_param = f"{field_info['field_path']}_max"

        q_obj = None

        # Get min value if present
        if min_param in self.request_data and self.request_data[min_param]:
            min_value = self._parse_datetime(self.request_data[min_param])
            if min_value:
                q_obj = Q(**{f"{field_info['field_path']}__gte": min_value})

        # Get max value if present
        if max_param in self.request_data and self.request_data[max_param]:
            max_value = self._parse_datetime(self.request_data[max_param])
            if max_value:
                max_q = Q(**{f"{field_info['field_path']}__lte": max_value})
                q_obj = max_q if q_obj is None else q_obj & max_q

        return q_obj

    def _build_search_filter(self) -> Optional[Q]:
        """Build Q object for text search across multiple fields"""
        search_term = self._get_field_values(SEARCH_PARAM)
        if not search_term or not isinstance(search_term, str):
            return None

        search_term = search_term.strip()
        if not search_term:
            return None

        q_obj = Q()

        # Find searchable fields
        for field_name, field_info in self.field_registry.items():
            if not field_info['searchable']:
                continue

            field_path = field_info["field_path"]
            # Handle text fields
            if field_info['type'] == 'text':
                q_obj |= Q(**{f"{field_path}__icontains": search_term})

            # Handle enum fields - search in enum labels
            elif field_info['type'] == 'enum' and field_info['enum_class']:
                enum_class = field_info['enum_class']
                matching_values = []

                # Try different enum interfaces
                if hasattr(enum_class, 'as_tuples'):
                    for enum_value, enum_label in enum_class.as_tuples():
                        if search_term.lower() in str(enum_label).lower():
                            matching_values.append(enum_value)
                elif hasattr(enum_class, 'choices'):
                    for choice in enum_class.choices:
                        if isinstance(choice, tuple) and len(choice) >= 2:
                            if search_term.lower() in str(choice[1]).lower():
                                matching_values.append(choice[0])

                if matching_values:
                    q_obj |= Q(**{f"{field_path}__in": matching_values})

        return q_obj

    def _apply_ordering(self) -> List[str]:
        """
        Apply ordering based on the ordering parameter.
        Returns a list of field names to use in order_by().
        """
        ordering_param = self._get_field_values(ORDERING_PARAM) or DEFAULT_ORDERING
        if not ordering_param:
            return []

        # Handle both string and list formats
        if isinstance(ordering_param, list):
            ordering_fields = ordering_param
        else:
            ordering_fields = [field.strip() for field in ordering_param.split(',') if field.strip()]

        valid_ordering = []

        for field in ordering_fields:
            # Handle descending order
            if field.startswith('-'):
                prefix = '-'
                field_name = field[1:]
            else:
                prefix = ''
                field_name = field

            # Check if field exists in our registry
            if field_name in self.field_registry:
                field_info = self.field_registry[field_name]
                valid_ordering.append(f"{prefix}{field_info['field_path']}")

        return valid_ordering

    def _parse_date(self, value: str) -> Optional[datetime.date]:
        """Parse string to date object"""
        if not value:
            return None

        formats = ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']
        for fmt in formats:
            try:
                return datetime.datetime.strptime(value, fmt).date()
            except ValueError:
                continue

        return None

    def _parse_datetime(self, value: str) -> Optional[datetime.datetime]:
        """Parse string to datetime object"""
        if not value:
            return None

        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M',
            '%d-%m-%Y %H:%M:%S',
            '%m/%d/%Y %H:%M:%S'
        ]
        for fmt in formats:
            try:
                return datetime.datetime.strptime(value, fmt)
            except ValueError:
                continue

        return None

    def _parse_advanced_filter(self) -> Optional[Q]:
        """
        Parse and build Q object from advanced filter parameter

        The advanced filter parameter should be a JSON string with the following structure:
        {
            "operator": "AND",  # can be "AND" or "OR"
            "conditions": [
                {
                    "field": "status",
                    "lookup": "exact",
                    "value": 1
                },
                {
                    "operator": "OR",
                    "conditions": [
                        {
                            "field": "is_vip",
                            "lookup": "exact",
                            "value": true
                        },
                        {
                            "field": "is_active",
                            "lookup": "exact",
                            "value": true
                        }
                    ]
                }
            ]
        }
        """
        filter_param = self._get_field_values(ADVANCED_FILTER_PARAM)
        if not filter_param:
            return None

        try:
            # URL decode the parameter
            if isinstance(filter_param, str):
                decoded_param = parse.unquote(filter_param)
                filter_config = json.loads(decoded_param)
            else:
                # If somehow it's already a dict/object
                filter_config = filter_param

            # Build filter Q object
            return self._build_filter_object(filter_config)

        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Error parsing advanced filter: {e}")
            return None

    def _build_filter_object(self, config: Dict) -> Optional[Q]:
        """
        Recursively build a Q object from the filter configuration
        """
        # If this is a group condition with an operator
        if 'operator' in config and 'conditions' in config:
            operator = config['operator'].upper()
            conditions = config['conditions']

            if not conditions:
                return None

            # Start with the first condition
            q_object = self._build_filter_object(conditions[0])
            if q_object is None:
                return None

            # Apply the operator to combine conditions
            for condition in conditions[1:]:
                next_q = self._build_filter_object(condition)

                if next_q is not None:
                    if operator == 'AND':
                        q_object &= next_q
                    elif operator == 'OR':
                        q_object |= next_q
                    else:
                        self.logger.warning(f"Unsupported operator: {operator}, using AND")
                        q_object &= next_q

            return q_object

        # If this is a leaf condition
        elif 'field' in config and 'value' in config:
            field = config['field']
            lookup = config.get('lookup')  # Lookup is optional, will use default if not provided
            value = config['value']

            # Validate field exists in model
            if field not in self.field_registry:
                self.logger.warning(f"Unknown field: {field}")
                return None

            # Build field filter
            return self._build_field_filter(field, value, lookup)

        else:
            self.logger.warning("Invalid filter condition format")
            return None

    def get_filterable_fields(self) -> Dict[str, Dict]:
        """
        Get information about all filterable fields for API documentation
        or frontend configuration.

        Returns:
            Dictionary of field names mapped to their metadata
        """
        fields = {}

        for field_name, field_info in self.field_registry.items():
            # Skip internal fields
            if field_name.startswith('_'):
                continue

            field_type = field_info['type']

            # Create metadata dict
            field_meta = {
                'name': field_name,
                'type': field_type,
                'filterable': True,
                'searchable': field_info['searchable'],
                'orderable': True,
                'lookups': field_info['lookups'],
                'default_lookup': field_info['default_lookup'],
            }

            # Add range filter flag if applicable
            if field_info['range_filter']:
                field_meta['range_filter'] = True

            # Add enum choices if available
            if field_type == 'enum' and field_info['enum_class']:
                enum_class = field_info['enum_class']
                choices = []

                if hasattr(enum_class, 'as_tuples'):
                    choices = [{'value': str(v), 'label': str(l)} for v, l in enum_class.as_tuples()]
                elif hasattr(enum_class, 'choices'):
                    choices = [{'value': str(v), 'label': str(l)} for v, l in enum_class.choices]

                if choices:
                    field_meta['choices'] = choices

            fields[field_name] = field_meta

        return fields

    def apply(self) -> 'ModelFilter':
        """Apply all filters and ordering to the queryset"""
        if self.filtered_queryset is not None:
            return self

        queryset = self.base_queryset
        query = Q()

        # Check for advanced filter
        advanced_q = self._parse_advanced_filter()
        if advanced_q:
            query &= advanced_q
        else:
            # Apply search filter if present
            search_q = self._build_search_filter()
            if search_q:
                query &= search_q

            # Process date/datetime range filters
            for field_name, field_info in self.field_registry.items():
                if not field_info['range_filter']:
                    continue

                field_type = field_info['type']

                if field_type == 'date':
                    date_range_q = self._build_date_range_filter(field_name)
                    if date_range_q:
                        query &= date_range_q
                elif field_type == 'datetime':
                    datetime_range_q = self._build_datetime_range_filter(field_name)
                    if datetime_range_q:
                        query &= datetime_range_q

            # Process regular field filters
            processed_fields = set()
            for param in self.request_data:
                # Skip special parameters
                if param in (SEARCH_PARAM, ORDERING_PARAM, ADVANCED_FILTER_PARAM):
                    continue
                if any(param.endswith(suffix) for suffix in DATE_RANGE_SUFFIXES):
                    continue

                elif param in self.field_registry and param not in processed_fields:
                    field_q = self._build_field_filter(param)
                    if field_q:
                        query &= field_q
                    processed_fields.add(param)

        # Apply filters to queryset
        self.filtered_queryset = queryset.filter(query)

        # Apply ordering
        ordering = self._apply_ordering()
        if ordering:
            self.filtered_queryset = self.filtered_queryset.order_by(*ordering)

        return self

    @property
    def qs(self):
        """Return the filtered and ordered queryset"""
        if self.filtered_queryset is None:
            self.apply()
        self.logger.info("Filtered Q object: %s", self.filtered_queryset.query.where)
        return self.filtered_queryset

    def get_filter_params(self) -> Dict:
        """
        Get the current filter parameters in a format suitable for saving

        Returns:
            Dictionary of filter parameters
        """
        params = {}

        # Include only real filter parameters (exclude pagination, etc.)
        for param, value in self.request_data.items():
            # Skip pagination, advanced filter, and ordering
            if param in ('page', 'page_size', ADVANCED_FILTER_PARAM, ORDERING_PARAM):
                continue

            params[param] = value

        # Include advanced filter if present
        if ADVANCED_FILTER_PARAM in self.request_data:
            try:
                decoded = parse.unquote(self.request_data[ADVANCED_FILTER_PARAM])
                params['_advanced_filter'] = json.loads(decoded)
            except (json.JSONDecodeError, ValueError):
                pass

        # Include ordering if present
        if ORDERING_PARAM in self.request_data:
            params['_ordering'] = self.request_data[ORDERING_PARAM]

        return params

    def to_url_params(self) -> str:
        """
        Convert current filter parameters to URL query string

        Returns:
            URL query string
        """
        params = []

        for key, value in self.request_data.items():
            if value:  # Skip empty values
                params.append(f"{key}={parse.quote(str(value))}")

        return '&'.join(params)
