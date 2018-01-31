import re

import django
from django.db import models
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
    def __init__(self, name, display_name=None, sort=None, tag=None, class_names="", style=""):
        d, li = None, None
        if isinstance(name, dict):
            d = name
            name = None

        elif isinstance(name, (list, tuple)):
            li = name
            name = None

        super().__init__(name=name, display_name=display_name, sort=sort, tag=tag, class_names=class_names, style=style)

        if d is not None:
            self.from_dict(d)
        elif li is not None:
            self.from_list(li)

        if self["display_name"] is None:
            self["display_name"] = str(self['name']).replace("_", " ").title()
        if self['sort'] is None:
            self['sort'] = str(self['name'])

    def from_dict(self, d):
        """Set the values from a dictionary"""
        self.update(d)

        name = self["name"]
        if self["display_name"] is None and name is not None:
            self["display_name"] = str(name).replace("_", " ").title()
        if self['sort'] is None and name is not None:
            self['sort'] = str(name)

    def from_list(self, li):
        length = len(li)
        if length > 0:
            self.name = li[0]
        if length > 1:
            self.display_name = li[1]
        if length > 2:
            self.sort = li[2]
        if length > 3:
            self.tag = li[3]
        if length > 4:
            self.class_names = li[4]
        if length > 5:
            self.style = li[5]

        name = self["name"]
        if self["display_name"] is None and name is not None:
            self["display_name"] = str(name).replace("_", " ").title()
        if self['sort'] is None and name is not None:
            self['sort'] = str(name)

    @property
    def name(self):
        return self["name"]

    @name.setter
    def name(self, name):
        self["name"] = name

    @property
    def display_name(self):
        return self["display_name"]

    @display_name.setter
    def display_name(self, name):
        self["display_name"] = name

    @property
    def sort(self):
        return self["sort"]

    @sort.setter
    def sort(self, sort):
        self["sort"] = sort

    @property
    def tag(self):
        return self["tag"]

    @tag.setter
    def tag(self, tag):
        self["tag"] = tag

    def safe_tag(self):
        """Return the tag without django braces and as a safe html string."""
        return mark_safe(self.tag.replace("{{ ", "").replace(" }}", "").replace("{{", "").replace("}}", ""))

    def parse_tag(self, obj, cell):
        """Parse a custom tag.

        Args:
             obj (object): Data object to render
             cell (str): object column value
        """
        tag = self.tag.replace("{{ ", "{{").replace(" }}", "}}")

        replace_vals = re.findall(r"\{([^{}]+)\}", tag)
        for val in replace_vals:
            try:
                if val.startswith('item.'):
                    value = getattr(obj, val[5:])
                    if callable(value):
                        value = value()
                elif val == "item":
                    value = obj
                else:
                    value = cell
                if value is None:
                    value = ""
                tag = tag.replace("{{" + val + "}}", str(value))
            except:
                tag = tag.replace("{{" + val + "}}", "")

        return tag

    @property
    def class_names(self):
        return self["class_names"]

    @class_names.setter
    def class_names(self, class_names):
        self["class_names"] = class_names

    @property
    def style(self):
        return self["style"]

    @style.setter
    def style(self, style):
        self["style"] = style


class TableOptions(object):
    def __init__(self, options=None):
        self.model = getattr(options, 'model', None)
        self.fields = getattr(options, 'fields', None)
        self.exclude = getattr(options, 'exclude', None)
        self.sortable = getattr(options, 'sortable', True)

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

        return new_class


class BaseTable(object):

    def __init__(self, queryset=None, ordering=None):
        self.queryset = queryset
        self.ordering = ordering
        if not hasattr(self, "base_columns"):
            self.base_columns = []
        self.columns = [d for d in self.base_columns]

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

    def render(self, obj, col):
        """Return the template html text for the row and column

        Args:
             obj (object): Data object to render
             col (Column): Column dictionary
        """
        cell = getattr(obj, col.name, "")
        if callable(cell):
            cell = cell()

        # Tag for ajax compatibility
        if col.tag:
            return mark_safe(col.parse_tag(obj, cell))

        elif hasattr(self, "render_"+col.name):
            return mark_safe(getattr(self, "render_"+col.name)(obj, cell))
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
