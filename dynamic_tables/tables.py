import copy
import re

import django
from django.db import models
from django.db.models import QuerySet
from django.db.models.functions import Lower, Upper
from django.utils import six
from django.utils.safestring import mark_safe

from collections import OrderedDict


__all__ = ["Column", "Table"]


def remote_field(field):
    """
    https://docs.djangoproject.com/en/1.9/releases/1.9/#field-rel-changes
    """
    if django.VERSION >= (1, 9):
        return field.remote_field
    return field.rel


def get_all_model_fields(model):
    opts = model._meta

    return [Column(f.name, f.verbose_name.title(), f.name)
            for f in sorted(opts.fields + opts.many_to_many)
            if not isinstance(f, models.AutoField) and not (getattr(remote_field(f), 'parent_link', False))]


class Column(dict):
    def __init__(self, name, display_name=None, order_by=None, tag=None, class_names="", style="", annotate=None):
        d, li = None, None
        if isinstance(name, dict):
            d = name
            name = None

        elif isinstance(name, (list, tuple)):
            li = name
            name = None

        super().__init__(name=name, display_name=display_name, order_by=order_by, tag=tag, class_names=class_names, style=style,
                         annotate=annotate)

        if d is not None:
            self.from_dict(d)
        elif li is not None:
            self.from_list(li)

        if self["display_name"] is None:
            self["display_name"] = str(self['name']).replace("_", " ").title()
        if self['order_by'] is None:
            self['order_by'] = str(self['name'])

    def from_dict(self, d):
        """Set the values from a dictionary"""
        self.update(d)

        name = self["name"]
        if self["display_name"] is None and name is not None:
            self["display_name"] = str(name).replace("_", " ").title()
        if self['order_by'] is None and name is not None:
            self['order_by'] = str(name)

    def from_list(self, li):
        length = len(li)
        if length > 0:
            self.name = li[0]
        if length > 1:
            self.display_name = li[1]
        if length > 2:
            self.order_by = li[2]
        if length > 3:
            self.tag = li[3]
        if length > 4:
            self.class_names = li[4]
        if length > 5:
            self.style = li[5]

        name = self["name"]
        if self["display_name"] is None and name is not None:
            self["display_name"] = str(name).replace("_", " ").title()
        if self['order_by'] is None and name is not None:
            self['order_by'] = str(name)

    def safe_tag(self):
        """Return the tag without django braces and as a safe html string."""
        return mark_safe(self.tag.replace("{{ ", "{{").replace(" }}", "}}").replace('"', '\\"').replace("'", "\\'"))

    def parse_tag(self, obj, cell, row_idx=None):
        """Parse a custom tag.

        Args:
             obj (object): Data object to render
             cell (str): object column value
             row_idx (int)[None]: Row index.
        """
        tag = self.tag.replace("{{ ", "{{").replace(" }}", "}}")

        replace_vals = re.findall(r"\{([^{}]+)\}", tag)
        for val in replace_vals:
            if val == "endif" or val == "else":
                continue

            # Check for if condition
            is_if_cond = False
            if val.startswith("if "):
                is_if_cond = True
                val = val[3:]

            # Get the value
            try:
                if val.startswith('item.'):
                    if isinstance(obj, dict) and val[5:] in obj:
                        value = obj[val[5:]]
                    else:
                        value = getattr(obj, val[5:])
                    if callable(value):
                        value = value()
                elif val == "item":
                    value = obj
                elif val == "row_idx":
                    value = row_idx
                else:
                    value = cell
                if value is None:
                    value = ""
            except:
                value = ""

            # Check if
            if is_if_cond:
                # Get the if condition positions
                start = tag.index("{{if "+val+"}}")
                end = tag.index("{{endif}}") + 9
                try:
                    else_idx = tag.index("{{else}}")
                except ValueError:
                    # The else condition was not found
                    else_idx = float("inf")

                if value:
                    if else_idx < end:
                        # Remove else part and remove the if condition
                        tag = tag[: else_idx] + tag[end:]
                        tag = tag.replace("{{if "+val+"}}", "", 1)
                    else:
                        # Remove the if condition (No else statement)
                        tag = tag.replace("{{if "+val+"}}", "", 1).replace("{{endif}}", "", 1)
                else:
                    if else_idx < end:
                        # Keep else part and remove if condition part
                        tag = tag[: start] + tag[else_idx + 8:]
                        tag = tag.replace("{{endif}}", "", 1)
                    else:
                        # Remove the entire if block without the value
                        tag = tag[:start] + tag[end:]

            # Set the value
            tag = tag.replace("{{" + val + "}}", str(value))

        return tag

    def __setattr__(self, key, value):
        self[key] = value

    def __dir__(self):
        return self.keys()

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


class TableOptions(object):
    def __init__(self, options=None):
        self.model = getattr(options, 'model', None)
        self.fields = getattr(options, 'fields', None)
        self.exclude = getattr(options, 'exclude', None)
        self.sortable = getattr(options, 'sortable', True)
        self.annotations = getattr(options, "annotations", {})

        self.table_id = getattr(options, 'table_id', "dynamic_table")
        self.table_class_names = getattr(options, 'table_class_names', "")
        self.table_style = getattr(options, 'table_style', "")
        self.row_class_names = getattr(options, 'row_class_names', "")
        self.row_style = getattr(options, 'row_style', "")


class TableMetaclass(type):
    def __new__(cls, name, bases, attrs):
        new_class = super(TableMetaclass, cls).__new__(cls, name, bases, attrs)
        new_class._meta = TableOptions(getattr(new_class, "Meta", None))
        new_class.base_columns = new_class.get_columns()
        new_class.annotations = copy.deepcopy(new_class._meta.annotations)

        return new_class


class BaseTable(object):

    order_by_name = "order_by"

    def __init__(self, queryset=None, order_by=None, parent=None):
        if not hasattr(self, "base_columns"):
            self.base_columns = []
        if not hasattr(self, "annotations"):
            self.annotations = {}
        self.columns = [d for d in self.base_columns]
        self.queryset = queryset
        self.order_by = None
        self.ordering = None
        self.set_ordering(order_by)

        self.queryset = self.get_queryset(queryset, parent=parent)

    def get_queryset(self, queryset, parent=None):
        """Take the original queryset and the possible parent object and return the queryset to be used."""
        return self.sort(self.annotate(queryset, parent=parent), parent=parent)

    def annotate(self, qs, parent=None):
        """Annotate the queryset from the column annotations."""
        annotate = copy.deepcopy(self.annotations)
        for col in self.columns:
            if col.annotate:
                if callable(col.annotate):
                    qs = col.annotate(col.name, qs, parent)
                else:
                    annotate[col.name] = col.annotate

        if len(annotate) == 0:
            return qs
        return qs.annotate(**annotate)

    def sort(self, qs, parent=None):
        """Sort the queryset."""
        if self.sortable and self.ordering:
            return qs.order_by(*self.order_by)
        return qs

    def set_ordering(self, order_by):
        self.ordering = order_by
        if order_by:
            self.order_by = self.get_ordering(order_by)

    @classmethod
    def get_ordering(cls, order_by):
        return tuple(cls._get_special_ordering(o) for o in order_by.split(','))

    @classmethod
    def _get_special_ordering(cls, sort_name):
        model = cls._meta.model
        col = sort_name

        # Check for a negative
        negative = False
        if col.startswith("-"):
            negative = True
            col = col[1:]

        # Get the field
        try:
            # Iterate over relations to get the field type
            sub_col = col
            while "__" in sub_col:
                sub_name, sub_col = sub_col.split("__", 1)
                sub = model._meta.get_field(sub_name)
                model = sub.target_field.model

            field = model._meta.get_field(sub_col)
        except:
            return sort_name

        # Check if some sort of text field (Do not do this for number field)
        if isinstance(field, (models.CharField, models.TextField, models.EmailField,
                              models.FileField, models.FilePathField, models.SlugField, models.URLField,
                              models.UUIDField, models.GenericIPAddressField)):
            if negative:
                return Upper(col).desc()
            return Upper(col)
        return sort_name

    @property
    def sortable(self):
        return self._meta.sortable

    @property
    def table_id(self):
        return self._meta.table_id

    @property
    def table_class_names(self):
        return self._meta.table_class_names

    @property
    def table_style(self):
        return self._meta.table_style

    @property
    def row_class_names(self):
        return self._meta.row_class_names

    @property
    def row_style(self):
        return self._meta.row_style

    @property
    def headers(self):
        return [d["display_name"] for d in self.columns]

    @classmethod
    def get_columns(cls):
        """
        Resolve the 'fields' argument that should be used for generating filters on the
        filterset. This is 'Meta.fields' sans the fields in 'Meta.exclude'.
        """
        model = cls._meta.model
        fields = cls._meta.fields
        exclude = cls._meta.exclude

        # No model specified - skip filter generation
        if not model:
            return OrderedDict()

        assert not (fields is None and exclude is None), \
            "Add an explicit 'Meta.fields' or 'Meta.exclude' to the %s class." % cls.__name__

        if fields is None or not fields:
            fields = get_all_model_fields(model)

        # Remove excluded fields
        exclude = exclude or []
        if not isinstance(fields, dict):
            flds = []
            for f in fields:
                col = Column(f)
                if col.name is not None and col.name not in exclude:
                    flds.append(col)

            fields = flds

        else:
            flds = []
            for f, lookups in fields.items():
                col = Column(f)
                col.from_dict(lookups)
                if col.name is not None and f not in exclude:
                    flds.append(col)
            fields = flds

        return fields

    def render(self, obj, col, row_idx=None):
        """Return the template html text for the row and column

        Args:
             obj (object): Data object to render
             col (Column): Column dictionary
             row_idx (int)[None]: Row index.
        """
        if isinstance(obj, dict):
            cell = obj.get(col.name, "")
        else:
            cell = getattr(obj, col.name, "")
        if callable(cell):
            cell = cell()

        # Tag for ajax compatibility
        if col.tag:
            return mark_safe(col.parse_tag(obj, cell, row_idx=row_idx))

        elif hasattr(self, "render_"+col.name):
            return mark_safe(getattr(self, "render_"+col.name)(obj, cell, row_idx=row_idx))
        else:
            return mark_safe(str(cell))


class Table(six.with_metaclass(TableMetaclass, BaseTable)):
    pass


# class CustomTable(Table):
#     class Meta:
#         model = None
#         fields = [('name1', 'display_name1'),
#                   'name2',
#                   ('name3', {"display_name": 'display_name3'}),
#                   {"name": 'name4', "display_name": 'display_name4'},
#
#                   {"name": 'name4', "display_name": 'display_name4',
#                    "tag": "<a href='{{item.get_absolute_url}}'>{{cell}}</a>"},
#                   ]
