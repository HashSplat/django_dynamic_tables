from django.core.exceptions import ImproperlyConfigured
from django.core.paginator import InvalidPage, Paginator
from django.db.models import Model, QuerySet, TextField, CharField, EmailField, FileField, SlugField, \
    URLField, UUIDField, GenericIPAddressField, FilePathField
from django.db.models.functions import Lower
from django.http import JsonResponse, Http404
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin


__all__ = ["SortableTableMixin", "PaginatorMixin", "AjaxableResponseMixin", "AjaxTableMixin"]


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
    def get_content_object(self, context):
        context_object_name = get_context_object_name(self)
        if isinstance(self, PaginatorMixin):
            context_content_name = self.get_context_paginated_name()
        elif isinstance(self, AjaxableResponseMixin):
            context_content_name = self.get_context_ajax_name()
        else:
            context_content_name = context_object_name

        # Return the content that may be manipulated
        if context_content_name in context:
            return context[context_content_name]

        # Get the content that may be manipulated
        qs = context[context_object_name]
        if context_object_name != context_content_name and hasattr(qs, context_content_name):
            try:
                qs = getattr(qs, context_content_name)
                qs = qs.all()
            except:
                pass
            context[context_content_name] = qs

        return qs

    def set_content_object(self, context, qs):
        context_object_name = get_context_object_name(self)
        if isinstance(self, PaginatorMixin):
            context_content_name = self.get_context_paginated_name()
        elif isinstance(self, AjaxableResponseMixin):
            context_content_name = self.get_context_ajax_name()
        else:
            context_content_name = context_object_name

        context[context_content_name] = qs


class SortableTableMixin(ViewMixin):
    """Works with a list view."""
    table = None
    context_table_name = "table"

    def _get_special_ordering(self, sort_name):
        col = sort_name
        negative = False
        if col.startswith("-"):
            negative = True
            col = col[1:]

        if self.table and self.table._meta.model:
            model = self.table._meta.model
        elif self.model:
            model = self.model
        else:
            return sort_name

        # Check if some sort of text field
        try:
            sub_col = col
            while "__" in sub_col:
                sub_name, sub_col = sub_col.split("__", 1)
                sub = model._meta.get_field(sub_name)
                model = sub.target_field.model
            field = model._meta.get_field(sub_col)
        except:
            return sort_name

        if isinstance(field, (CharField, TextField, EmailField, FileField, FilePathField,
                              SlugField, URLField, UUIDField, GenericIPAddressField)):
            if negative:
                return Lower(col).desc()
            return Lower(col)
        return sort_name

    def get_ordering(self):
        if self.request.method == "GET":
            if "sort" in self.request.GET:
                # Note Char ordering is affected by capitalization. Lower removes that
                ordering = tuple(self._get_special_ordering(sort) for sort in self.request.GET.get("sort").split(","))
                return ordering
        try:
            return super().get_ordering()
        except AttributeError:
            return None

    def get_order_names(self):
        if self.request.method == "GET":
            if "sort" in self.request.GET:
                return tuple(self.request.GET.get("sort").split(","))
        return tuple()

    def set_content_object(self, context, qs):
        super().set_content_object(context, qs)
        if self.context_table_name in context:
            context[self.context_table_name].queryset = qs

    def sort_table(self, context):
        qs = self.get_content_object(context)
        if not isinstance(self, MultipleObjectMixin):  # Had default ordering
            ordering = self.get_ordering()
            if ordering is not None:
                qs = qs.order_by(*ordering)
        table = self.table(qs, ordering=self.get_order_names())
        context[self.context_table_name] = table
        self.set_content_object(context, qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.table:  # Support for django-tables2. This doesn't work with pagination thought :/
            self.sort_table(context)
        return context


class PaginatorMixin(ViewMixin):
    context_paginated_name = None
    allow_empty = True
    paginate_by = None
    paginate_orphans = 0
    paginator_class = Paginator
    page_kwarg = 'page'
    ordering = None

    def paginate_queryset(self, queryset, page_size):
        """Paginate the queryset, if needed."""
        paginator = self.get_paginator(
            queryset, page_size, orphans=self.get_paginate_orphans(),
            allow_empty_first_page=self.get_allow_empty())
        page_kwarg = self.page_kwarg
        page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1
        try:
            page_number = int(page)
        except ValueError:
            if page == 'last':
                page_number = paginator.num_pages
            else:
                raise Http404("Page is not 'last', nor can it be converted to an int.")
        try:
            page = paginator.page(page_number)
            return (paginator, page, page.object_list, page.has_other_pages())
        except InvalidPage as e:
            raise Http404(('Invalid page (%(page_number)s): %(message)s') % {
                'page_number': page_number,
                'message': str(e)
            })

    def get_paginate_by(self, queryset):
        """
        Get the number of items to paginate by, or ``None`` for no pagination.
        """
        return self.paginate_by

    def get_paginator(self, queryset, per_page, orphans=0,
                      allow_empty_first_page=True, **kwargs):
        """Return an instance of the paginator for this view."""
        return self.paginator_class(
            queryset, per_page, orphans=orphans,
            allow_empty_first_page=allow_empty_first_page, **kwargs)

    def get_paginate_orphans(self):
        """
        Return the maximum number of orphans extend the last page by when
        paginating.
        """
        return self.paginate_orphans

    def get_allow_empty(self):
        """
        Return ``True`` if the view should display empty lists and ``False``
        if a 404 should be raised instead.
        """
        return self.allow_empty

    def get_context_paginated_name(self):
        return self.context_paginated_name or get_context_object_name(self)

    def add_paginator(self, context, queryset, context_object_name=None, page_size=None):
        if context_object_name is None:
            context_object_name = self.get_context_paginated_name()
        context_paginated_name = context_object_name
        if page_size is None:
            page_size = self.get_paginate_by(queryset)

        paginator = None
        page = None
        is_paginated = False
        if page_size:
            paginator, page, queryset, is_paginated = self.paginate_queryset(queryset, page_size)

        context["paginator"] = paginator
        context["page_obj"] = page
        context["is_paginated"] = is_paginated
        context[context_paginated_name] = queryset
        self.set_content_object(context, queryset)

        return context

    def paginate(self, context):
        qs = self.get_content_object(context)
        self.add_paginator(context, qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.paginate_by and not isinstance(self, MultipleObjectMixin):  # generic.ListView has pagination built in
            self.paginate(context)
        return context


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

    def format_json_data(self, data):
        if isinstance(data, QuerySet):
            return [self.format_json_data(obj) for obj in data]
        elif isinstance(data, Model):
            d = {field.attname: getattr(data, field.attname) for field in data._meta.fields}
            try:
                d["get_absolute_url"] = data.get_absolute_url()
            except (AttributeError, Exception):
                pass
            try:
                d["get_update_url"] = data.get_update_url()
            except (AttributeError, Exception):
                pass
            d["str"] = str(data)

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["has_ajax_support"] = True
        context["context_ajax_name"] = self.get_context_ajax_name()
        return context
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
        if hasattr(form.instance, "user") and not form.instance.user:
            form.instance.user = self.request.user

        response = super().form_valid(form)
        if self.request.is_ajax():
            data = self.get_post_ajax_data()
            return JsonResponse(data)
        else:
            return response
    # ========== END POST Method ==========


class FilterMixin(ViewMixin):
    """Support for django-filter"""
    filter_class = None
    context_filter_name = 'filter'

    def __init__(self, *args, **kwargs):
        self.filter = None
        super().__init__(*args, **kwargs)

    def filter_qs(self, qs):
        filt = self.filter_class(self.request.GET, queryset=qs)
        return filt, filt.qs

    def get_queryset(self):
        qs = super().get_queryset()
        if isinstance(self, MultipleObjectMixin):
            if self.filter_class:
                self.filter, qs = self.filter_qs(qs)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.filter_class and not isinstance(self, MultipleObjectMixin):  # generic.ListView uses get_queryset
            qs = self.get_content_object(context)
            self.filter, qs = self.filter_qs(qs)
            context[self.context_filter_name] = self.filter
            self.set_content_object(context, qs)

        return context


class AjaxTableMixin(AjaxableResponseMixin, PaginatorMixin, SortableTableMixin, FilterMixin):
    """View mixin that has Ajax with sorting and pagination"""
    pass
