# Django Dynamic Tables
A quick way to add sortable paginated tables with ajax support.

## Basic Setup
### Include in INSTALLED_APPS
```python
INSTALLED_APPS = [
    ...
    'dynamic_tables',
]
```

### Create tables
models.py
```python
from django.db import models

class MyModel(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(default="", blank=True, null=True)
    age = models.PositiveIntegerField()
   

class Other(models.Model):
    mymodel = models.ForeignKey(MyModel, on_delete=models.CASCADE)
    thing1 = models.CharField(max_length=50)
    thing2 = models.CharField(max_length=50)
    thing3 = models.CharField(max_length=50)
    
    def get_thing1_alt(self):
        return "thing1_alt"
```

tables.py
```python
from dynamic_tables import Table, Column
from .models import MyModel


class MyTable(Table):
    class Meta:
        model = MyModel
        fields = ["name", "age"]
```

views.py
```python
from django.views import generic
from dynamic_tables import PaginatorMixin, AjaxableResponseMixin, SortableTableMixin

from .models import MyModel
from .table import MyTable


class MyView(AjaxableResponseMixin, SortableTableMixin, generic.ListView):
    model = MyModel
    table = MyTable
    context_object_name = "obj"
    template_name = 'myapp/myapp_list.html'
    paginate_by = 10  # normal generic.ListView pagination
```

myapp/myapp_list.html
```
{% extends "base.html" %}
{% load render_table from dynamic_tables %}

<h4>{{ obj }}</h4>

{% render_table table use_load_more=True %}
```


## Advanced Usage
tables.py
```python
from dynamic_tables import Table, Column
from .models import MyModel, Other


class MyTable(Table):
    class Meta:
        model = MyModel
        fields = [Column("name",  # name=Accessor
                         "Display Name",  # display_name=Name to display for the column header
                         sort="name",   # sort=order_by field usually the same as name (automatic). If False do not sort
                         tag="<a href='{{ item.get_absolute_url }}'>{{ cell }}</a>"),  # Custom cell html tag. Works with ajax too
                  Column("age", sort=False),
                  ("description", "Info")  # Automatically uses description to sort
                  ]
                  

class ATable(Table):
    class Meta:
        model = Other
        exclude = ["mymodel"]


class OtherTable(Table):
    class Meta:
        model = Other
        fields = [Column("thing1", "Thing 1", "thing1",
                         tag="<a href='{{ item.get_thing1_alt }}'>{{ cell }}</a>"),
                  Column("thing2", sort="mymodel__name"),  # Warning when sorting from a foreignkey specify the field or the ID is used for sorting
                  "thing3",
                  ]
```


views.py
```python
from django.views import generic
from dynamic_tables import PaginatorMixin, AjaxableResponseMixin, SortableTableMixin

from .models import MyModel, Other
from .table import MyTable, OtherTable


class OtherView(AjaxableResponseMixin, PaginatorMixin, SortableTableMixin, generic.DetailView):
    model = MyModel
    table = OtherTable  # Use the OtherTable because the Table will be the Other reverse ForeignKey queryset
    context_object_name = "obj"
    template_name = 'myapp/myapp_detail.html'
    paginate_by = 10  # uses PaginatorMixin
    context_paginated_name = "other_set"  # SortableTableMixin will use this queryset because of PaginatorMixin
    context_ajax_name = "other_set"  # The name to access the json name for the ajax json respons
    # (If this is not given it defaults to the context_paginated_name) 

    @classmethod
    def get_json_data(cls, data_obj, obj_json):
        # Need to add some extra data for json to work properly.
        # Fields are loaded automatically this is used for functions and attributes that are in the table
        # but are not fields.
        obj_json["get_thing1_alt"] = str(data_obj.get_thing1_alt())

    # Does below automatically by context_object_name and context_paginated_name being different
    # def paginate(self, context):
    #     self.add_paginator(context, context["obj"].other_set.all())
```
