HELPER_SETTINGS = {
    "TIME_ZONE": "America/Chicago",
    "INSTALLED_APPS": [
        "djangocms_versioning",
        "djangocms_content_expiry",

    ],
    "MIGRATION_MODULES": {
        "auth": None,
        "cms": None,
        "menus": None,
        "djangocms_content_expiry": None,
        "djangocms_versioning": None,
    },
    "CMS_PERMISSION": True,
    "LANGUAGES": (
        ("en", "English"),
        ("de", "German"),
        ("fr", "French"),
        ("it", "Italiano"),
    ),
    "CMS_LANGUAGES": {
        1: [
            {"code": "en", "name": "English", "fallbacks": ["de", "fr"]},
            {
                "code": "de",
                "name": "Deutsche",
                "fallbacks": ["en"],  # FOR TESTING DO NOT ADD 'fr' HERE
            },
            {
                "code": "fr",
                "name": "Française",
                "fallbacks": ["en"],  # FOR TESTING DO NOT ADD 'de' HERE
            },
            {
                "code": "it",
                "name": "Italiano",
                "fallbacks": ["fr"],  # FOR TESTING, LEAVE AS ONLY 'fr'
            },
        ]
    },
    "PARLER_ENABLE_CACHING": False,
    "LANGUAGE_CODE": "en",
}


def run():
    from djangocms_helper import runner

    runner.cms("djangocms_content_expiry", extra_args=[])


if __name__ == "__main__":
    run()
