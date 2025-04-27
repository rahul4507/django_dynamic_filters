from django.test import TestCase, RequestFactory
from django.http import QueryDict

from django_dynamic_filters.filters import ModelFilter
from tests.models import Product, Category


class ModelFilterTests(TestCase):
    def setUp(self):
        # Create test data
        self.category1 = Category.objects.create(name="Electronics")
        self.category2 = Category.objects.create(name="Books")

        self.product1 = Product.objects.create(
            name="Laptop",
            description="Powerful laptop",
            price=1299.99,
            category=self.category1,
            is_active=True
        )

        self.product2 = Product.objects.create(
            name="Phone",
            description="Smartphone",
            price=799.99,
            category=self.category1,
            is_active=True
        )

        self.product3 = Product.objects.create(
            name="Python Book",
            description="Learn Python programming",
            price=49.99,
            category=self.category2,
            is_active=True
        )

        self.product4 = Product.objects.create(
            name="Old Phone",
            description="Discontinued model",
            price=299.99,
            category=self.category1,
            is_active=False
        )

        self.factory = RequestFactory()

    def test_simple_field_filter(self):
        # Test exact match filter
        query_dict = QueryDict("name=Laptop")

        filter_obj = ModelFilter(
            model=Product,
            request_data=query_dict
        )

        results = filter_obj.apply().qs
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].name, "Laptop")

    def test_range_filter(self):
        # Test price range filter
        query_dict = QueryDict("price_min=300&price_max=1000")

        filter_obj = ModelFilter(
            model=Product,
            request_data=query_dict
        )

        results = filter_obj.apply().qs
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].name, "Phone")

    def test_search_filter(self):
        # Test search across multiple fields
        query_dict = QueryDict("search=python")

        filter_obj = ModelFilter(
            model=Product,
            request_data=query_dict
        )

        results = filter_obj.apply().qs
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].name, "Python Book")

    def test_relation_filter(self):
        # Test filtering by related model
        query_dict = QueryDict(f"category={self.category2.id}")

        filter_obj = ModelFilter(
            model=Product,
            request_data=query_dict
        )

        results = filter_obj.apply().qs
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].name, "Python Book")

    def test_boolean_filter(self):
        # Test boolean filter
        query_dict = QueryDict("is_active=false")

        filter_obj = ModelFilter(
            model=Product,
            request_data=query_dict
        )

        results = filter_obj.apply().qs
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].name, "Old Phone")

    def test_advanced_filter(self):
        # Test advanced filter with AND/OR conditions
        advanced_filter = {
            "operator": "AND",
            "conditions": [
                {"field": "category", "lookup": "exact", "value": self.category1.id},
                {
                    "operator": "OR",
                    "conditions": [
                        {"field": "price", "lookup": "gt", "value": 1000},
                        {"field": "is_active", "lookup": "exact", "value": False}
                    ]
                }
            ]
        }

        import json
        from urllib.parse import quote

        query_dict = QueryDict(f"filter={quote(json.dumps(advanced_filter))}")

        filter_obj = ModelFilter(
            model=Product,
            request_data=query_dict
        )

        results = filter_obj.apply().qs
        self.assertEqual(results.count(), 2)
        self.assertTrue("Laptop" in [p.name for p in results])
        self.assertTrue("Old Phone" in [p.name for p in results])