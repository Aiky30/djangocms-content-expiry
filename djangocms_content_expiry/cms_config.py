from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html

from cms.app_base import CMSAppConfig, CMSAppExtension
from cms.models import PageContent

from .cache import (
    get_changelist_page_content_exclusion_cache,
    set_changelist_page_content_exclusion_cache,
)
from .constants import CONTENT_EXPIRY_EXPIRE_FIELD_LABEL


try:
    from djangocms_alias.models import AliasContent
    djangocms_alias_enabled = True
except ImportError:
    djangocms_alias_enabled = False


def get_moderation_content_expiry_link(obj):
    """
    Return a user friendly button for viewing content expiry in the
    actions section of the Moderation Request Admin Changelist
    in djangocms-moderation.

    :param obj: A Moderation Request object supplied from the admin view table row
    :return: A link to the expiry record if one exists
    """
    version = obj.moderation_request.version

    # If a content expiry record exists we can go to it
    if hasattr(version, "contentexpiry"):
        view_endpoint = format_html(
            "{}?collection__id__exact={}&_popup=1",
            reverse("admin:djangocms_content_expiry_contentexpiry_change", args=[version.contentexpiry.pk]),
            obj.pk,
        )
        return render_to_string(
            "djangocms_content_expiry/calendar_icon.html", {"url": view_endpoint, "field_id": f"contentexpiry_{obj.pk}"}
        )
    return ""


def get_expiry_date(obj):
    """
    A custom field to show the expiry date in the
    Moderation Request Admin Changelist in djangocms-moderation.

    :param obj: A Moderation Request object supplied from the admin view table row
    :return: The expiry date from the matching moderation request object
    """
    version = obj.moderation_request.version

    if hasattr(version, "contentexpiry"):
        return version.contentexpiry.expires


get_expiry_date.short_description = CONTENT_EXPIRY_EXPIRE_FIELD_LABEL


def get_copy_content_expiry_button(obj):
    """
    Return a user friendly link to copy a content expiry to other Moderation Request Items
    link redirects to view which handles this
    """
    version = obj.moderation_request.version

    if hasattr(version, "contentexpiry"):
        content_expiry = version.contentexpiry
        view_endpoint = format_html(
            "{}?collection__id={}&moderation_request__id={}&_popup=1",
            reverse("admin:djangocms_moderation_moderationrequesttreenode_copy"),
            obj.moderation_request.collection.pk,
            obj.moderation_request.pk,
        )
        return render_to_string(
            "djangocms_content_expiry/admin/icons/calendar_copy_icon.html", {
                "url": view_endpoint,
                "content_expiry_id": f"content_expiry_{content_expiry.pk}",
                "moderation_request_id": f"moderation_request_{obj.moderation_request.pk}"
            }
        )
    return ""


def content_expiry_site_page_content_excluded_set(queryset, request):
    """
    Filter ContentExpiry records to show only PageContent objects available on a given site.
    Model structure: Expiry->Version->Content->Page->Node->Site

    :param queryset: A queryset object of ContentExpiry records
    :param request: A request object if one exists
    :return: A filtered list of Content Expiry records minus any none site PageContent models
    """
    current_site = get_current_site(request)
    page_content_ctype = ContentType.objects.get_for_model(PageContent)
    pagecontent_exclusion_list = get_changelist_page_content_exclusion_cache(current_site.pk)

    if not pagecontent_exclusion_list:
        pagecontent_set = PageContent._original_manager.exclude(page__node__site=current_site)
        pagecontent_set.select_related('page__node')

        pagecontent_exclusion_list = pagecontent_set.values_list('id', flat=True)
        set_changelist_page_content_exclusion_cache(pagecontent_exclusion_list, current_site.pk)

    return queryset.exclude(
        version__content_type=page_content_ctype, version__object_id__in=pagecontent_exclusion_list
    )


def _get_excluded_alias_site_list(site):
    """
    Get a list of Alias objects that cannot be viewed by the current site

    :param site: A site object to query against
    :return: A filtered list of alias objects
    """
    alias_exclusion_set = AliasContent._original_manager.exclude(Q(alias__site=site) | Q(alias__site__isnull=True))
    alias_exclusion_set.select_related('alias')
    return alias_exclusion_set.values_list('id', flat=True)


def content_expiry_site_alias_excluded_set(queryset, request):
    """
    Filter ContentExpiry records to show only Alias objects available on a given site.
    Alias is added as part of Content Expiry because it is considered a "Core" package, the same as
    djangocms_versioning. All other packages should define their own configuration.
    Model structure: Expiry->Version->Content->Alias->site

    :param queryset: A queryset object of ContentExpiry records
    :param request: A request object if one exists
    :return: A filtered list of Content Expiry records minus any none site PageContent models
    """
    current_site = get_current_site(request)
    alias_content_ctype = ContentType.objects.get_for_model(AliasContent)
    alias_exclusion_set = _get_excluded_alias_site_list(current_site)

    return queryset.exclude(
      version__content_type=alias_content_ctype, version__object_id__in=alias_exclusion_set
    )


def my_third_party_function_1(request):

    return {
        "encoding":
    }


class ContentExpiryExtension(CMSAppExtension):
    def __init__(self):
        self.expiry_changelist_queryset_filters = []
        self.expiry_export_file_configuration = []

    def configure_app(self, cms_config):
        versioning_enabled = getattr(cms_config, "djangocms_versioning_enabled", False)
        moderation_enabled = getattr(cms_config, "djangocms_moderation_enabled", False)
        expiry_changelist_queryset_filters = getattr(
            cms_config, "djangocms_content_expiry_changelist_queryset_filters", [])
        expiry_export_file_configuration = getattr(
            cms_config, "djangocms_content_expiry_expiry_export_file_configuration", {})

        if not versioning_enabled:
            raise ImproperlyConfigured("Versioning needs to be enabled for Content Expiry")

        if not moderation_enabled:
            raise ImproperlyConfigured("Moderation needs to be enabled for Content Expiry")

        self.expiry_changelist_queryset_filters.extend(expiry_changelist_queryset_filters)
        self.expiry_changelist_queryset_filters.extend(expiry_changelist_queryset_filters)


class ContentExpiryAppConfig(CMSAppConfig):
    # Enable moderation to be able to "configure it"
    djangocms_moderation_enabled = True
    moderated_models = []
    moderation_request_changelist_actions = [
        get_moderation_content_expiry_link,
        get_copy_content_expiry_button,
    ]
    moderation_request_changelist_fields = [
        get_expiry_date,
    ]
    # Enable versioning because moderation is versioning dependant
    djangocms_versioning_enabled = True
    versioning = []

    djangocms_content_expiry_enabled = getattr(
        settings, "DJANGOCMS_CONTENT_EXPIRY_ENABLED", True
    )
    djangocms_content_expiry_changelist_queryset_filters = [
        content_expiry_site_page_content_excluded_set,
    ]

    if djangocms_alias_enabled:
        djangocms_content_expiry_changelist_queryset_filters.append(
            content_expiry_site_alias_excluded_set
        )
