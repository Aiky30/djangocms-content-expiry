import csv
import datetime

from django.conf.urls import url
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html_join
from django.utils.translation import ugettext_lazy as _

from djangocms_versioning.helpers import get_preview_url

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
    list_display_links = None
    list_filter = (ContentTypeFilter, ('expires', ContentExpiryDateRangeFilter), VersionStateFilter, AuthorFilter)
    form = ContentExpiryForm
    change_list_template = "djangocms_content_expiry/admin/change_list.html"

    class Media:
        css = {
            'all': (
                'djangocms_content_expiry/css/actions.css',
                'djangocms_content_expiry/css/date_filter.css',
                'djangocms_content_expiry/css/multiselect_filter.css',
            )
        }

    def has_add_permission(self, *args, **kwargs):
        # Entries are added automatically
        return False

    def has_delete_permission(self, *args, **kwargs):
        # Deletion should never be possible, the only way that a
        # content expiry record could be deleted is via versioning.
        return False

    def get_list_display(self, request):
        return [
            "title",
            "content_type",
            "expires",
            "version_state",
            "version_author",
            self.list_display_actions(request),
        ]

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        return [
            url(
                r'^export_csv/$',
                self.admin_site.admin_view(self.export_to_csv),
                name="{}_{}_export_csv".format(*info),
            ),
        ] + super().get_urls()

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

    def list_display_actions(self, request):
        """
        A closure that makes it possible to pass request object to
        list action button functions.
        """
        actions = [
            self._get_preview_link,
            self._get_edit_link,
        ]

        def list_actions(obj):
            """
            Display links to state change endpoints
            """
            return format_html_join(
                "", "{}", ((action(obj, request),) for action in actions)
            )

        list_actions.short_description = _("actions")
        return list_actions

    def _get_preview_url(self, obj):
        """
        Return the preview method if available, otherwise get a preview url
        from the content with the help of versioning

        :return: preview url
        """
        content_obj = obj.version.content
        if hasattr(content_obj, "get_preview_url"):
            return content_obj.get_preview_url()
        return get_preview_url(content_obj)

    def _get_preview_link(self, obj, request):
        preview_url = self._get_preview_url(obj)

        return render_to_string(
            "djangocms_content_expiry/admin/icons/preview_action_icon.html", {
                "url": preview_url,
            }
        )

    def _get_edit_link(self, obj, request):
        archive_url = reverse(
            "admin:{app}_{model}_change".format(
                app=obj._meta.app_label, model=self.model._meta.model_name
            ),
            args=(obj.pk,),
        )

        return render_to_string(
            "djangocms_content_expiry/admin/icons/edit_action_icon.html", {
                "url": archive_url,
            }
        )

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
