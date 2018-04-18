from django.core.exceptions import ImproperlyConfigured
from django.core.paginator import InvalidPage, Paginator
from django.db.models import Model, QuerySet, TextField, CharField, EmailField, FileField, SlugField, \
    URLField, UUIDField, GenericIPAddressField, FilePathField
from django.db.models.functions import Lower
from django.http import JsonResponse, Http404
from django.urls import reverse
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin, MultipleObjectTemplateResponseMixin
from django.views.generic import edit

__all__ = ["FilterMixin", "SortableTableMixin", "PaginatorMixin", "AjaxableResponseMixin",
           "PaginatedTableMixin", "AjaxTableMixin",
           "FormMixin", "FormListView"]


def get_context_object_name(view):
    """Return the context_object_name for a view or None."""
    try:
        if isinstance(view, MultipleObjectMixin):
            return view.get_context_object_name(object_list=view.object_list)
        elif isinstance(view, SingleObjectMixin):
            return view.get_context_object_name(view.object)
        else:
            return view.get_context_object_name()
    except:
        try:
            return view.get_context_object_name()
        except:
            pass

    try:
        return view.context_object_name
    except:
        pass


class ViewMixin(object):
    context_content_name = None
    model = None

    def __init__(self, *args, **kwargs):
        self.content_parent = None
        self.content_raw = None
        self._modified_qs = None

        # Prevent AttributeError
        if not hasattr(self, "request"):
            self.request = None
        if isinstance(self, MultipleObjectMixin):
            self.object_list = None
        elif isinstance(self, SingleObjectMixin):
            self.object = None

        super().__init__(*args, **kwargs)

    def get_context_content_name(self):
        return self.context_content_name

    def get_queryset(self):
        """Return the queryset."""
        try:
            return super().get_queryset()
        except AttributeError:
            pass
        return self.model.objects.all()

    def get_view_queryset(self, queryset=None):
        """Get and modify the content queryset."""
        # Get the queryset or parent object
        if hasattr(self, 'get_object'):
            qs = self.get_object(queryset=queryset)
        else:
            qs = self.get_queryset()
        obj = self.content_parent = qs

        # Check if the view queryset is retrieved from the obj
        context_object_name = get_context_object_name(self)
        context_content_name = self.get_context_content_name()
        if context_content_name and context_object_name != context_content_name and hasattr(obj, context_content_name):
            try:
                qs = getattr(obj, context_content_name)
                if callable(qs):
                    qs = qs()
                else:
                    qs = qs.all()
            except:
                pass

        self.content_raw = qs
        return self.modify_queryset(qs, parent=obj)

    get_content_object = get_view_queryset

    def _modify_queryset(self, qs, **kwargs):
        """Actually modify the queryset."""
        return qs

    def _end_modify_queryset(self, qs, **kwargs):
        """Final modifications to the queryset. Some modifications may come after other modifications."""
        return qs

    def modify_queryset(self, qs, **kwargs):
        """Method to modify a queryset and store the queryset in self._modified_qs. Ever parent call to this method that
        does modify the queryset should set self._modified_qs.
        """
        qs = self._modify_queryset(qs, **kwargs)
        qs = self._end_modify_queryset(qs, **kwargs)
        self._modified_qs = qs
        return qs

    def set_content_object(self, context, qs, **kwargs):
        context["modified_qs"] = qs
        context[self.get_context_content_name() or get_context_object_name(self)] = qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self._modified_qs is None:
            self._modified_qs = self.get_view_queryset()
        if self._modified_qs is not None:
            self.set_content_object(context, self._modified_qs, **kwargs)

        return context


class FilterMixin(ViewMixin):
    """Support for django-filter"""
    filter_class = None
    context_filter_name = 'filter'

    def __init__(self, *args, **kwargs):
        self._filter = None
        super().__init__(*args, **kwargs)

    def filter_qs(self, qs):
        filt = self.filter_class(self.request.GET, queryset=qs)
        return filt, filt.qs

    def _modify_queryset(self, qs, page_size=None, **kwargs):
        """Actually modify the queryset."""
        qs = super()._modify_queryset(qs)

        if qs is not None and self.filter_class:
            self._filter, qs = self.filter_qs(qs)

        return qs

    def modify_queryset(self, qs, **kwargs):
        """Method to modify a queryset and store the queryset in self._modified_qs. Ever parent call to this method that
        does modify the queryset should set self._modified_qs.
        """
        qs = super().modify_queryset(qs, **kwargs)

        # No more modifications should happen at this point. Save the final qs value.
        if self._filter and self.filter_class:
            self._filter._qs = qs  # self._filter.qs is a property without a setter. set the underlying qs variable.

        return qs

    def set_content_object(self, context, qs, **kwargs):
        super().set_content_object(context, qs, **kwargs)
        context[self.context_filter_name] = self._filter


class PaginatorMixin(ViewMixin):
    context_paginated_name = None
    allow_empty = True
    paginate_by = None
    paginate_orphans = 0
    paginator_class = Paginator
    page_kwarg = 'page'
    ordering = None

    def get_context_content_name(self):
        return super().get_context_content_name() or self.get_context_paginated_name()

    def get_context_paginated_name(self):
        return self.context_paginated_name or get_context_object_name(self)

    def __init__(self, *args, **kwargs):
        self._paginator = None
        self._page_queryset = None
        self._page = None
        self._is_paginated = None
        super().__init__(*args, **kwargs)

    # ===== Pagination Methods from ListView =====
    get_paginate_by = MultipleObjectMixin.get_paginate_by
    get_paginator = MultipleObjectMixin.get_paginator
    get_paginate_orphans = MultipleObjectMixin.get_paginate_orphans
    get_allow_empty = MultipleObjectMixin.get_allow_empty

    def _paginate_queryset(self, queryset, page_size):
        try:
            # Call parent paginate ListView (This could also be from SortableTableMixin which calls parent method)
            paginator, page, queryset, is_paginated = super(PaginatorMixin, self).paginate_queryset(queryset, page_size)
        except AttributeError as err:
            if 'paginate_queryset' in str(err):
                # SortableTableMixin paginate_queryset was called, but ListView is not a base class
                paginator, page, queryset, is_paginated = MultipleObjectMixin.paginate_queryset(self, queryset, page_size)
            else:
                # Attribute error did not have to do with a non existing 'paginate_queryset' method.
                raise AttributeError(str(err)) from err

        return paginator, page, queryset, is_paginated

    def paginate_queryset(self, queryset, page_size):
        """Paginate the queryset, if needed (Sort the queryset first).

        This method fixes issues if ListView is a base class.
        """
        if self._modified_qs is None and self.paginate_by:
            queryset = self.modify_queryset(queryset, page_size=page_size)
            return self._paginator, self._page, queryset, self._is_paginated

        return self._paginate_queryset(queryset, page_size)
    # ===== END Pagination Methods from ListView =====

    def add_paginator(self, context, queryset, context_object_name=None, page_size=None):
        """Paginate the queryset and return context, paginator, page, queryset, is_paginated."""
        # Paginate
        paginator = None
        page = None
        is_paginated = False
        if page_size is None:
            page_size = self.paginate_by
        if page_size is not None:
            paginator, page, queryset, is_paginated = self._paginate_queryset(queryset, page_size=page_size)

        # Set the paginate context object
        if self._paginator:
            context["paginator"] = self._paginator
            context["page_obj"] = self._page
            context["is_paginated"] = self._is_paginated

            if context_object_name is None:
                context_object_name = self.get_context_paginated_name()
            context[context_object_name] = queryset

        return context, paginator, page, queryset, is_paginated

    def paginate(self, context):
        """Get the content object, paginate, and return context, paginator, page, queryset, is_paginated."""
        qs = self.get_content_object()
        if qs is not None:
            return self.add_paginator(context, qs)
        return context, None, None, qs, None

    def _end_modify_queryset(self, qs, page_size=None, **kwargs):
        """Final modifications to the queryset. Some modifications may come after other modifications."""
        qs = super()._end_modify_queryset(qs, **kwargs)

        if qs is not None and self.paginator_class:
            paginator = None
            page = None
            is_paginated = False
            if page_size is None:
                page_size = self.get_paginate_by(qs)
            if page_size:
                paginator, page, qs, is_paginated = self._paginate_queryset(qs, page_size)

            self._paginator = paginator
            self._page_queryset = qs
            self._page = page
            self._is_paginated = is_paginated

        return qs

    def modify_queryset(self, qs, **kwargs):
        """Method to modify a queryset and store the queryset in self._modified_qs. Ever parent call to this method that
        does modify the queryset should set self._modified_qs.
        """
        qs = super().modify_queryset(qs, **kwargs)
        self._page_queryset = qs
        return qs

    def set_content_object(self, context, qs, context_object_name=None,
                           paginator=None, page=None, is_paginated=False, **kwargs):
        super().set_content_object(context, qs, **kwargs)

        context["paginator"] = self._paginator
        context["page_obj"] = self._page
        context["is_paginated"] = self._is_paginated

        if context_object_name is None:
            context_object_name = self.get_context_paginated_name()
        context[context_object_name] = qs


class SortableTableMixin(PaginatorMixin):
    """Works with a list view."""
    table = None
    context_table_name = "table"
    order_by_name = "order_by"

    def __init__(self, *args, **kwargs):
        self._table = None
        super().__init__(*args, **kwargs)

    def get_order_by_name(self):
        if self.order_by_name:
            return self.order_by_name
        return self.table.order_by_name

    def get_order_by(self):
        order_by_name = self.get_order_by_name()
        return self.request.GET.get(order_by_name, None)

    def _modify_queryset(self, qs, order_by=None, **kwargs):
        """Actually modify the queryset."""
        qs = super()._modify_queryset(qs, **kwargs)

        if qs is not None and self.table:
            if order_by is None:
                order_by = self.get_order_by()
            self._table = self.table(qs, order_by=order_by, parent=self.content_parent)
            qs = self._table.queryset

        return qs

    def modify_queryset(self, qs, **kwargs):
        """Method to modify a queryset and store the queryset in self._modified_qs. Ever parent call to this method that
        does modify the queryset should set self._modified_qs.
        """
        qs = super().modify_queryset(qs, **kwargs)
        if self._table:
            self._table.queryset = qs
        return qs

    def set_content_object(self, context, qs, **kwargs):
        super().set_content_object(context, qs, **kwargs)
        context[self.context_table_name] = self._table


class AjaxableResponseMixin(ViewMixin):
    """Easily add Ajax support to a view.

    Using the GET method (ListView, DetailView):
        context_ajax_name (str/list): String or list of string names to return as json
            data from the context
        get_context_ajax_name (function): Same as context_ajax_name

        context_object_name (str): ListView and DetailView uses this and this is used by default to get the json
            data
        get_context_object_name (function): Alternative function for context_object_name

        get_json_data (function): Convert a Model objects data into a json dictionary (json_dict) that is returned
            in the json response.

        get_ajax_data (function): Return a dictionary to customize the json data in the json response.

    Using the POST method (FormView, CreateView, UpdateView):
        get_post_ajax_data (function): Automatically returns the object that was updated.

        get_json_data (function): Convert a Model objects data into a json dictionary (json_dict) that is returned
            in the json response.
    """
    context_ajax_name = None

    def __init__(self, *args, **kwargs):
        self._paginator = None
        self._page = None
        self._row_idx = None
        super().__init__(*args, **kwargs)

    def get_context_content_name(self):
        return super().get_context_content_name() or self.get_context_ajax_name()

    # ========== GET Method ==========
    def get_json_data(self, data_obj, json_dict):
        """Convert a Model objects data into a json dictionary (json_dict) that is returned in the json response.

        Args:
            data_obj (Model): Database row/Model object. Get data from this object and put it in data_dict.
            json_dict (dict): Json response dictionary to hold data from the data object. Add data to this object

        Returns:
            json_dict (dict): Object dictionary to give to the JsonResponse
        """
        # d["str"] = str(data)
        return json_dict

    @staticmethod
    def getattr_or_value(obj, attr):
        try:
            value = getattr(obj, attr)
            if callable(value):
                return value()
            return value
        except:
            return None

    def format_json_data(self, data):
        if isinstance(data, QuerySet):
            return [self.format_json_data(obj) for obj in data]
        elif isinstance(data, Model):
            d = {}

            # Defaults
            try:
                if self._row_idx is None:
                    if self._paginator and self._page:
                        self._row_idx = self._paginator.per_page * (self._page.number - 1)
                else:
                    self._row_idx += 1
                d["row_idx"] = self._row_idx
            except (AttributeError, Exception):
                pass
            try:
                d["get_absolute_url"] = data.get_absolute_url()
            except (AttributeError, Exception):
                pass
            try:
                d["get_update_url"] = data.get_update_url()
            except (AttributeError, Exception):
                pass
            d["str"] = str(data)

            # Capture fields
            fields = [field.attname for field in data._meta.fields]
            if isinstance(self, SortableTableMixin):
                if self._table:
                    fields.extend([col.name for col in self._table.columns if col.name not in fields])
                elif self.table:
                    fields.extend([col.name for col in self.table.base_columns if col.name not in fields])

            d.update({field: self.getattr_or_value(data, field) for field in fields})

            # Update the json_dict (d) or replace it by returning a new json_dict
            alt_data = self.get_json_data(data, d)
            if isinstance(alt_data, dict):
                d = alt_data
            return d
        else:
            return data

    def get_context_ajax_name(self):
        """Returns a list of ajax context names to return in json."""
        if self.context_ajax_name:
            return self.context_ajax_name
        elif isinstance(self, PaginatorMixin):
            return self.get_context_paginated_name()
        return None

    def _get_context_ajax_names(self):
        """Return a list of ajax context object names."""
        # Get the ajax context name from method
        ajax_context_name = self.get_context_ajax_name()

        # Check value or get_context_object_name
        if ajax_context_name is None:
            ajax_context_name = get_context_object_name(self)
            if not ajax_context_name:
                return None

        # Make iterable
        if not isinstance(ajax_context_name, (list, tuple)):
            return [ajax_context_name]
        return ajax_context_name

    def get_ajax_data(self, context):
        """Return the ajax data for the GET request."""
        ajax_context_names = self._get_context_ajax_names()
        if ajax_context_names:
            data = {name: self.format_json_data(context.get(name, None)) for name in ajax_context_names}
            return data
        else:
            raise ImproperlyConfigured(
                "%(cls)s is missing a ajax context name. Define "
                "%(cls)s.context_ajax_name, %(cls)s.context_object_name, or override "
                "%(cls)s.get_context_ajax_name(), (cls)s.get_context_object_name()." % {
                    'cls': self.__class__.__name__
                }
            )

    def get(self, request, *args, **kwargs):
        if request.is_ajax():
            if isinstance(self, MultipleObjectMixin):
                self.object_list = self.get_queryset()
                kwargs["object_list"] = self.object_list
            elif isinstance(self, SingleObjectMixin):
                self.object = self.get_object()
                kwargs["object"] = self.object
            context = self.get_context_data(**kwargs)
            data = self.get_ajax_data(context)
            return JsonResponse(data, status=200)
        else:
            return super().get(request, *args, **kwargs)

    def set_content_object(self, context, qs, **kwargs):
        super().set_content_object(context, qs, **kwargs)

        context[self.get_context_ajax_name()] = qs
        context["has_ajax_support"] = True
        context["context_ajax_name"] = self.get_context_ajax_name()
    # ========== END GET Method ==========

    # ========== POST Method ==========
    def form_invalid(self, form):
        response = super(AjaxableResponseMixin, self).form_invalid(form)
        if self.request.is_ajax():
            return JsonResponse(form.errors, status=400)
        else:
            return response

    def get_post_ajax_data(self):
        """Return the ajax data after a successful POST request."""
        return self.format_json_data(self.object)

    def form_valid(self, form):
        # Set the user for the form if not given
        if hasattr(form, "instance") and hasattr(form.instance, "user") and not form.instance.user:
            form.instance.user = self.request.user

        response = super().form_valid(form)
        if self.request.is_ajax():
            data = self.get_post_ajax_data()
            return JsonResponse(data)
        else:
            return response
    # ========== END POST Method ==========


class PaginatedTableMixin(SortableTableMixin, FilterMixin):
    """A paginated table mixin (without ajax support, cannot use "Load More")."""
    pass


class AjaxTableMixin(AjaxableResponseMixin, PaginatedTableMixin):
    """View mixin that has Ajax with sorting and pagination"""
    pass


# ========== FormView ==========
class FormMixin(ViewMixin):
    """Use this class with a dynamic_tables.QuerysetForm. Alternatively, you can override "get_form_kwargs()" to get
    a queryset and call "modify_queryset(queryset)".
    """
    model = None
    form_class = None
    form_queryset_kwarg = "queryset"
    template_name_suffix = '_merge'  # template_name = "app/model_merge.html"

    def __init__(self, *args, **kwargs):
        self._modified_qs = None
        self.object_list = None
        self.object = None
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = super().get_form_kwargs()

        if self.form_queryset_kwarg not in kwargs:
            if hasattr(self.form_class, "get_initial_queryset"):
                qs = self.form_class.get_initial_queryset()
            elif self.model:
                qs = self.model.objects.all()
            else:
                qs = None
            if self.request.method == "GET":
                qs = self.modify_queryset(qs)
            kwargs[self.form_queryset_kwarg] = qs

        return kwargs

    def get_success_url(self):
        """Return the URL to redirect to after processing a valid form."""
        if not self.success_url:
            raise ImproperlyConfigured("No URL to redirect to. Provide a success_url.")
        success_url = str(self.success_url)

        # Check if "app:name" was given
        if ":" in success_url and not success_url.rsplit(":", 1)[-1].isdigit():
            success_url = reverse(success_url)
        return success_url  # success_url may be lazy

    def form_valid(self, form):
        self.object = form.save()
        return super().form_valid(form)


class FormListView(FormMixin, edit.SingleObjectTemplateResponseMixin, edit.BaseFormView):
    pass


class ModelFormView(FormMixin, edit.ModelFormMixin, edit.SingleObjectTemplateResponseMixin, edit.BaseFormView):
    pass
