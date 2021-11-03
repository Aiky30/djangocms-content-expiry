from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
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


def content_expiry_site_page_content_excluded_set(site, queryset):
    """
    Filter ContentExpiry records to show only PageContent objects available on a given site.
    Model structure: Expiry->Version->Content->Page->Node->Site

    :param site: A site object to query against
    :param queryset: A queryset object of ContentExpiry records
    :return: A filtered list of Content Expiry records minus any none site PageContent models
    """
    page_content_ctype = ContentType.objects.get_for_model(PageContent)
    pagecontent_exclusion_list = get_changelist_page_content_exclusion_cache()

    if not pagecontent_exclusion_list:
        pagecontent_set = PageContent._original_manager.exclude(page__node__site=site)
        pagecontent_set.select_related('page__node')

        pagecontent_exclusion_list = pagecontent_set.values('pk')
        set_changelist_page_content_exclusion_cache(pagecontent_exclusion_list)

    return queryset.exclude(
        version__content_type=page_content_ctype, version__object_id__in=pagecontent_exclusion_list
    )


class ContentExpiryExtension(CMSAppExtension):
    def __init__(self):
        self.expiry_changelist_queryset_filters = []

    def configure_app(self, cms_config):
        versioning_enabled = getattr(cms_config, "djangocms_versioning_enabled", False)
        moderation_enabled = getattr(cms_config, "djangocms_moderation_enabled", False)
        expiry_changelist_queryset_filters = getattr(
            cms_config, "djangocms_content_expiry_changelist_queryset_filters", [])

        if not versioning_enabled:
            raise ImproperlyConfigured("Versioning needs to be enabled for Content Expiry")

        if not moderation_enabled:
            raise ImproperlyConfigured("Moderation needs to be enabled for Content Expiry")

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
