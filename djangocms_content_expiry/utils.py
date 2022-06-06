from django.apps import apps
from django.contrib.contenttypes.models import ContentType

from dateutil.relativedelta import relativedelta
from djangocms_versioning.datastructures import VersionableItemAlias

from .conf import DEFAULT_CONTENT_EXPIRY_DURATION
from .models import DefaultContentExpiryConfiguration


def _get_version_content_model_content_type(version):
    """
    Returns a content type that describes the content
    """
    # Otherwise, use the content type registered by the version
    return version.content_type


def get_default_duration_for_version(version):
    """
    Returns a default expiration value dependant on whether an entry exists for
    a content type in DefaultContentExpiryConfiguration.
    """
    content_type = _get_version_content_model_content_type(version)
    default_configuration = DefaultContentExpiryConfiguration.objects.filter(
        content_type=content_type
    )
    if default_configuration:
        return relativedelta(months=default_configuration[0].duration)
    return relativedelta(months=DEFAULT_CONTENT_EXPIRY_DURATION)


def get_future_expire_date(version, date):
    """
    Returns a date that will expire after a default period that can differ per content type
    """
    return date + get_default_duration_for_version(version)


def get_versionable_content_types():
    """
    Returns a list of content type objects that are versioned
    """
    content_types = []
    versioning_config = apps.get_app_config("djangocms_versioning")

    for versionable in versioning_config.cms_extension.versionables:
        if not isinstance(versionable, VersionableItemAlias):
            content_type = ContentType.objects.get_for_model(versionable.content_model)
            content_types.append(content_type)
    return content_types


def get_file_export_settings(request):
    """
    Returns a dictionary of settings for the csv writer:
        https://docs.python.org/3/library/csv.html#examples
    """
    settings = {}
    app_config = apps.get_app_config("djangocms_versioning")
    settings = app_config.cms_extension.file_export_settings
    for _callable in app_config.cms_extension.file_export_settings:
        result = _callable(request)
        settings = {**settings, **result}
    return settings
