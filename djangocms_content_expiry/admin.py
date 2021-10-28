import csv
import datetime
import operator

from django.conf.urls import url
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Q

from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _

from functools import reduce

from .conf import DEFAULT_CONTENT_EXPIRY_EXPORT_DATE_FORMAT
from .filters import (
    AuthorFilter,
    ContentExpiryDateRangeFilter,
    ContentTypeFilter,
    VersionStateFilter,
)
from .forms import ContentExpiryForm, DefaultContentExpiryConfigurationForm
from .helpers import get_rangefilter_expires_default
from .models import ContentExpiry, DefaultContentExpiryConfiguration


@admin.register(ContentExpiry)
class ContentExpiryAdmin(admin.ModelAdmin):
    list_display = ['title', 'content_type', 'expires', 'version_state', 'version_author']
    list_filter = (ContentTypeFilter, ('expires', ContentExpiryDateRangeFilter), VersionStateFilter, AuthorFilter)
    form = ContentExpiryForm
    change_list_template = "djangocms_content_expiry/admin/change_list.html"

    class Media:
        css = {
            'all': ('djangocms_content_expiry/css/date_filter.css',
                    'djangocms_content_expiry/css/multiselect_filter.css',)
        }

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        # For each content type with site limit the queryset
        current_site = get_current_site(request)
        """
        for content_type in _cms_extension().versionables_by_content:
            value = ContentType.objects.get_for_model(content_type)
        
        """
        filters = []

        # PageContent = Expiry->Version->Content->Page->Node->Site
        from cms.models import PageContent
        def get_page_content_site_objects(site):
            page_queryset = PageContent._original_manager.exclude(page__node__site=site)
            return page_queryset.select_related('page__node')

        # Get all content types for site
        # https://docs.djangoproject.com/en/3.2/ref/contrib/contenttypes/#reverse-generic-relations
        page_content_ctype = ContentType.objects.get_for_model(PageContent)
        site_page_contents = get_page_content_site_objects(current_site)
        queryset = queryset.exclude(
            version__content_type=page_content_ctype, version__object_id__in=site_page_contents
        )

        # Alias = Expiry->Version->Content->Alias->site
        from djangocms_alias.models import AliasContent
        def get_alias_content_site_objects(site):
            alias_queryset = AliasContent._original_manager.exclude(Q(alias__site=site) | Q(alias__site__isnull=True))
            #queryset = AliasContent._original_manager.filter(alias__site=site, alias__site__isnull=False))
            return alias_queryset.select_related('alias')

        # Get all content types for site
        # https://docs.djangoproject.com/en/3.2/ref/contrib/contenttypes/#reverse-generic-relations
        alias_content_ctype = ContentType.objects.get_for_model(AliasContent)
        site_alias_contents = get_alias_content_site_objects(current_site)
        queryset = queryset.exclude(
            version__content_type=alias_content_ctype, version__object_id__in=site_alias_contents
        )

        # Navigation = Expiry->Version->Content->Menu->site

        # queryset = ContentExpiry.objects.filter(
        #     reduce(operator.or_, filters)
        # )

        return queryset

    def has_add_permission(self, *args, **kwargs):
        # Entries are added automatically
        return False

    def has_delete_permission(self, *args, **kwargs):
        # Deletion should never be possible, the only way that a
        # content expiry record could be deleted is via versioning.
        return False

    def get_rangefilter_expires_default(self, *args, **kwargs):
        return get_rangefilter_expires_default()

    def get_rangefilter_expires_title(self, *args, **kwargs):
        return _("By Expiry Date Range")

    def title(self, obj):
        """
        A field to display the content objects title
        """
        return obj.version.content
    title.short_description = _('Title')

    def content_type(self, obj):
        """
        A field to display the content type as a readable representation
        """
        return ContentType.objects.get_for_model(
            obj.version.content
        )
    content_type.short_description = _('Content type')

    def version_state(self, obj):
        """
        A field to display the version state as a readable representation
        """
        return obj.version.get_state_display()
    version_state.short_description = _('Version state')

    def version_author(self, obj):
        """
        A field to display the author of the version
        """
        return obj.version.created_by
    version_author.short_description = _('Version author')

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        return [
            url(
                r'^export_csv/$',
                self.admin_site.admin_view(self.export_to_csv),
                name="{}_{}_export_csv".format(*info),
            ),
        ] + super().get_urls()

    def _format_export_datetime(self, date, date_format=DEFAULT_CONTENT_EXPIRY_EXPORT_DATE_FORMAT):
        """
        date: DateTime object
        date_format: String, date time string format for strftime

        Returns a formatted human readable date time string
        """
        if isinstance(date, datetime.date):
            return date.strftime(date_format)
        return ""

    def export_to_csv(self, request):
        """
        Retrieves the queryset and exports to csv format
        """
        queryset = self.get_exported_queryset(request)
        meta = self.model._meta
        field_names = ['Title', 'Content Type', 'Expiry Date', 'Version State', 'Version Author']
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format(meta)
        writer = csv.writer(response)
        writer.writerow(field_names)

        for row in queryset:
            title = row.version.content
            content_type = ContentType.objects.get_for_model(row.version.content)
            expiry_date = self._format_export_datetime(row.expires)
            version_state = row.version.get_state_display()
            version_author = row.version.created_by
            writer.writerow([title, content_type, expiry_date, version_state, version_author])

        return response

    def get_exported_queryset(self, request):
        """
        Returns export queryset by respecting applied filters.
        """
        list_display = self.get_list_display(request)
        list_display_links = self.get_list_display_links(request, list_display)
        list_filter = self.get_list_filter(request)
        search_fields = self.get_search_fields(request)
        changelist = self.get_changelist(request)

        changelist_kwargs = {
            'request': request,
            'model': self.model,
            'list_display': list_display,
            'list_display_links': list_display_links,
            'list_filter': list_filter,
            'date_hierarchy': self.date_hierarchy,
            'search_fields': search_fields,
            'list_select_related': self.list_select_related,
            'list_per_page': self.list_per_page,
            'list_max_show_all': self.list_max_show_all,
            'list_editable': self.list_editable,
            'model_admin': self,
            'sortable_by': self.sortable_by
        }
        cl = changelist(**changelist_kwargs)

        return cl.get_queryset(request)


@admin.register(DefaultContentExpiryConfiguration)
class DefaultContentExpiryConfigurationAdmin(admin.ModelAdmin):
    list_display = ['content_type', 'duration']
    form = DefaultContentExpiryConfigurationForm
