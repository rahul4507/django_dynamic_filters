# Django Dynamic Filter

A flexible and powerful dynamic filtering solution for Django projects that enables complex query building with minimal configuration.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [Usage Examples](#usage-examples)
- [Configuration Options](#configuration-options)
- [API Reference](#api-reference)
- [Field Types and Lookups](#field-types-and-lookups)
- [Advanced Filtering](#advanced-filtering)
- [Custom Models](#custom-models)
- [Contributing](#contributing)

## Installation

```bash
pip install django-dynamic-filter
```

Add `'django_dynamic_filter'` to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'django_dynamic_filter',
    # ...
]
```

## Quick Start

### 1. Use the filterable fields in your models

```python
from django.db import models
from django_dynamic_filter.fields import CharField, IntegerField, DateTimeField

class Product(models.Model):
    name = CharField(max_length=100, filter_config={'searchable': True})
    price = IntegerField(filter_config={'range_filter': True})
    created_at = DateTimeField(auto_now_add=True, filter_config={'range_filter': True})
    # ...
```

### 2. Use the dynamic filter manager with your model

```python
from django_dynamic_filter.managers import DynamicFilterManager

class Product(models.Model):
    # ...fields
    
    objects = DynamicFilterManager()
```

### 3. Apply filters in your views

```python
def product_list(request):
    products = Product.objects.apply_filtering(request.GET)
    return render(request, 'products/list.html', {'products': products})
```

### 4. Use in your API views

```python
from rest_framework.views import APIView
from rest_framework.response import Response

class ProductListAPI(APIView):
    def get(self, request):
        products = Product.objects.apply_filtering(request.GET)
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)
```

## Core Concepts

### Field Registry

The package maintains a registry of all fields in your model, including:
- Native model fields
- Related model fields
- Annotated fields in querysets

Each field is analyzed to determine:
- Field type (text, integer, date, etc.)
- Available lookup expressions
- Default lookup expression
- Whether it supports range filtering
- Whether it's searchable

### Filter Configuration

Filter configuration can be specified in multiple ways:

1. At the field level using `filter_config`:
   ```python
   name = CharField(max_length=100, filter_config={'searchable': True})
   ```

2. At the queryset level when applying filters:
   ```python
   queryset.apply_filtering(filter_config={"search_fields": ["name", "description"]})
   ```

### Request Parameters

The package understands various request parameters:

- Regular field filters: `?name=value`
- Range filters: `?price_min=10&price_max=100`
- Search filter: `?search=keyword`
- Ordering: `?ordering=field,-other_field`
- Advanced filter: `?filter={"operator":"AND","conditions":[...]}`

## Usage Examples

### Basic Filtering

```python
# URL: /products/?name=coffee&category=beverages
products = Product.objects.apply_filtering(request.GET)
```

### Searching

```python
# URL: /products/?search=organic coffee
products = Product.objects.apply_filtering(request.GET)
```

### Range Filtering

```python
# URL: /products/?price_min=10&price_max=50&created_at_min=2023-01-01
products = Product.objects.apply_filtering(request.GET)
```

### Ordering

```python
# URL: /products/?ordering=price,-created_at
products = Product.objects.apply_filtering(request.GET)
```

### Filtering with Annotations

```python
from django.db.models import F, Value
from django.db.models.functions import Concat

products = (
    Product.objects
    .annotate(
        full_name=Concat('brand__name', Value(' '), 'name')
    )
    .apply_filtering(
        filter_config={"search_fields": ["full_name", "description"]}
    )
)
```

### Soft Delete Models

```python
from django_dynamic_filter.managers import SoftDeleteManager
from django_dynamic_filter.models import SoftDeleteModel

class Product(SoftDeleteModel):
    # ... fields
    
    objects = SoftDeleteManager()
    
# Get non-deleted products with filtering
products = Product.objects.apply_filtering(request.GET)

# Include deleted products
all_products = Product.objects.all_with_deleted()

# Only get deleted products
deleted_products = Product.objects.only_deleted()
```

## Configuration Options

### Field Configuration Options

```python
field = CharField(
    filter_config={
        'searchable': True,       # Include in free-text search
        'filterable': True,       # Allow direct filtering (default: True)
        'lookups': ['exact', 'icontains'],  # Available lookup expressions
        'default': 'icontains',   # Default lookup to use
        'range_filter': True,     # Enable range filtering
    }
)
```

### Filter Application Configuration

```python
queryset.apply_filtering({
    "filter_fields": ["name", "category", "price"],  # Fields to allow filtering on
    "search_fields": ["name", "description"],        # Fields to include in text search
    "exclude_fields": ["internal_id"]                # Fields to exclude from filtering
})
```

## API Reference

### Fields

All standard Django field types are supported with the `FilterableFieldMixin`:

```python
from django_dynamic_filter.fields import (
    CharField, TextField, IntegerField, BooleanField, DateField, 
    DateTimeField, ForeignKey, ManyToManyField, JSONField
)
```

### Managers

#### `DynamicFilterManager`

A manager that provides dynamic filtering capabilities:

```python
class MyModel(models.Model):
    objects = DynamicFilterManager()
    
    # ...
```

Methods:
- `apply_filtering(request_data=None, filter_config=None)`: Apply filters to the queryset

#### `SoftDeleteManager`

Manager for models with soft delete functionality:

```python
class MyModel(SoftDeleteModel):
    objects = SoftDeleteManager()
    
    # ...
```

Methods:
- `all_with_deleted()`: Return all records including deleted ones
- `only_deleted()`: Return only deleted records
- `apply_filtering(request_data=None, filter_config=None)`: Apply filters to non-deleted records

### QuerySets

#### `DynamicFilterQuerySet`

QuerySet with dynamic filtering capabilities:

Methods:
- `apply_filtering(request_data=None, filter_config=None)`: Apply filters to the queryset

#### `SoftDeleteQuerySet`

QuerySet that implements soft delete functionality:

Methods:
- `delete()`: Soft delete all objects in the queryset

### Models

#### `SoftDeleteModel`

An abstract model that implements soft delete functionality:

```python
class MyModel(SoftDeleteModel):
    # ...
```

Fields:
- `is_deleted`: Boolean field to mark record as deleted
- `deleted_at`: DateTime field for deletion timestamp

## Field Types and Lookups

The package maps Django field types to simplified types that determine available lookup expressions:

| Field Type | Default Lookup | Available Lookups | Range Filter |
|------------|---------------|------------------|-------------|
| text       | icontains     | exact, iexact, contains, icontains, startswith, istartswith | No |
| integer    | exact         | exact, gt, gte, lt, lte, in, range | Yes |
| decimal    | exact         | exact, gt, gte, lt, lte, range | Yes |
| boolean    | exact         | exact | No |
| date       | exact         | exact, gt, gte, lt, lte, range | Yes |
| datetime   | exact         | exact, gt, gte, lt, lte, range, date | Yes |
| enum       | exact         | exact, in | No |
| relation   | exact         | exact, in | No |
| json       | has_key       | has_key, contains, contained_by | No |
| array      | contains      | contains, contained_by, overlap, len | No |

## Advanced Filtering

The package supports advanced filtering via a JSON structure:

```
?filter={"operator":"AND","conditions":[
  {"field":"status","lookup":"exact","value":1},
  {"operator":"OR","conditions":[
    {"field":"is_vip","lookup":"exact","value":true},
    {"field":"is_active","lookup":"exact","value":true}
  ]}
]}
```

This enables complex nested conditions that can't be expressed with URL query parameters alone.

## Custom Models

### Create a base model with filtering and soft delete

```python
from django.db import models
from django_dynamic_filter.managers import SoftDeleteManager
from django_dynamic_filter.models import SoftDeleteModel

class BaseModel(SoftDeleteModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = SoftDeleteManager()
    
    class Meta:
        abstract = True

# Use in your models
class Product(BaseModel):
    name = CharField(max_length=100, filter_config={'searchable': True})
    # ...
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Clone the repository
2. Create a virtual environment
3. Install development dependencies: `pip install -e ".[dev]"`
4. Run tests: `pytest`