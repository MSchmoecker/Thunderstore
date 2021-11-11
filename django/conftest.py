import io
import json
import threading
from copy import copy
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer as SuperHTTPServer
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from thunderstore.account.forms import CreateServiceAccountForm
from thunderstore.account.models import ServiceAccount
from thunderstore.community.models import (
    Community,
    CommunitySite,
    PackageCategory,
    PackageListing,
    PackageListingSection,
)
from thunderstore.core.factories import UserFactory
from thunderstore.core.types import UserType
from thunderstore.core.utils import ChoiceEnum
from thunderstore.repository.factories import (
    PackageFactory,
    PackageVersionFactory,
    TeamFactory,
    TeamMemberFactory,
)
from thunderstore.repository.models import (
    Package,
    Team,
    TeamMember,
    TeamMemberRole,
    Webhook,
)
from thunderstore.usermedia.tests.utils import create_and_upload_usermedia
from thunderstore.webhooks.models import WebhookType


class HTTPServer(SuperHTTPServer):
    """
    Class for wrapper to run SimpleHTTPServer on Thread.
    Ctrl +Only Thread remains dead when terminated with C.
    Keyboard Interrupt passes.
    """

    def run(self):
        try:
            self.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.server_close()


class PostHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        return


@pytest.fixture()
def http_server():
    host, port = "localhost", 8888
    url = f"http://{host}:{port}/"
    server = HTTPServer((host, port), PostHTTPRequestHandler)
    thread = threading.Thread(None, server.run)
    thread.start()
    yield url
    server.shutdown()
    thread.join()


@pytest.fixture()
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="Test",
        email="test@example.org",
        password="hunter2",
    )


@pytest.fixture()
def team():
    return Team.objects.create(name="Test_Team")


@pytest.fixture()
def team_member(team):
    return TeamMember.objects.create(
        team=team,
        user=UserFactory(),
        role=TeamMemberRole.member,
    )


@pytest.fixture()
def team_owner(team):
    return TeamMember.objects.create(
        team=team,
        user=UserFactory(),
        role=TeamMemberRole.owner,
    )


@pytest.fixture()
def package(team):
    return Package.objects.create(
        owner=team,
        name="Test_Package",
    )


@pytest.fixture()
def package_version(package):
    return PackageVersionFactory.create(
        package=package,
        name=package.name,
        version_number="1.0.0",
        website_url="https://example.org",
        description="Example mod",
        readme="# This is an example mod",
    )


@pytest.fixture(scope="function")
def manifest_v1_data():
    return {
        "name": "name",
        "version_number": "1.0.0",
        "website_url": "",
        "description": "",
        "dependencies": [],
    }


@pytest.fixture(scope="function")
def active_package():
    package = PackageFactory.create(
        is_active=True,
        is_deprecated=False,
    )
    PackageVersionFactory.create(
        name=package.name,
        package=package,
        is_active=True,
    )
    return package


@pytest.fixture(scope="function")
def active_package_listing(community, active_package):
    return PackageListing.objects.create(
        community=community,
        package=active_package,
    )


@pytest.fixture(scope="function")
def active_version(active_package):
    return active_package.versions.first()


@pytest.fixture(scope="function")
def active_version_with_listing(community, active_package):
    PackageListing.objects.create(
        community=community,
        package=active_package,
    )
    return active_package.versions.first()


@pytest.fixture()
def release_webhook(community_site):
    return Webhook.objects.create(
        name="test",
        webhook_url="https://example.com/",
        webhook_type=WebhookType.mod_release,
        is_active=True,
        community_site=community_site,
    )


@pytest.fixture()
def community():
    return Community.objects.create(name="Test", identifier="test")


@pytest.fixture()
def package_category(community):
    return PackageCategory.objects.create(
        name="Test",
        slug="test",
        community=community,
    )


@pytest.fixture()
def package_listing_section(community):
    return PackageListingSection.objects.create(
        community=community,
        name="Test Section",
        slug="test-section",
        is_listed=True,
    )


@pytest.fixture()
def site():
    return Site.objects.create(domain="testsite.test", name="Testsite")


@pytest.fixture()
def community_site(community, site):
    return CommunitySite.objects.create(site=site, community=community)


@pytest.fixture()
def celery_app():
    from celery import Celery, _state

    app = Celery("thunderstore", set_as_current=False)
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.autodiscover_tasks(force=True)
    on_app_finalizers = copy(_state._on_app_finalizers)
    yield app
    _state._deregister_app(app)
    # Registering a new task creates a hook that adds it to all future app
    # instances, meaning that we need to restore the hooks to pre-test
    # state as to not spill over tasks to other tests
    _state._on_app_finalizers = on_app_finalizers


@pytest.fixture(autouse=True)
def _use_static_files_storage(settings):
    settings.STATICFILES_STORAGE = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


@pytest.fixture()
def service_account(user, team) -> ServiceAccount:
    TeamMember.objects.create(
        user=user,
        team=team,
        role=TeamMemberRole.owner,
    )
    form = CreateServiceAccountForm(
        user,
        data={"team": team, "nickname": "Nickname"},
    )
    assert form.is_valid()
    return form.save()


@pytest.fixture()
def api_client(community_site) -> APIClient:
    return APIClient(HTTP_HOST=community_site.site.domain)


@pytest.fixture(scope="session")
def manifest_v1_package_bytes() -> bytes:
    icon_raw = io.BytesIO()
    icon = Image.new("RGB", (256, 256), "#FF0000")
    icon.save(icon_raw, format="PNG")

    readme = "# Test readme".encode("utf-8")
    manifest = json.dumps(
        {
            "name": "name",
            "version_number": "1.0.0",
            "website_url": "",
            "description": "",
            "dependencies": [],
        }
    ).encode("utf-8")

    files = [
        ("README.md", readme),
        ("icon.png", icon_raw.getvalue()),
        ("manifest.json", manifest),
    ]

    zip_raw = io.BytesIO()
    with ZipFile(zip_raw, "a", ZIP_DEFLATED, False) as zip_file:
        for name, data in files:
            zip_file.writestr(name, data)

    return zip_raw.getvalue()


@pytest.fixture(scope="function")
def manifest_v1_package_upload_id(
    manifest_v1_package_bytes: bytes,
    api_client: APIClient,
    user: UserType,
    settings: Any,
) -> str:
    checks_disabled = settings.DISABLE_TRANSACTION_CHECKS
    settings.DISABLE_TRANSACTION_CHECKS = True
    upload_id = create_and_upload_usermedia(
        api_client=api_client,
        user=user,
        settings=settings,
        upload=manifest_v1_package_bytes,
    )
    settings.DISABLE_TRANSACTION_CHECKS = checks_disabled
    return upload_id


def create_test_service_account_user():
    team_owner = UserFactory()
    team = TeamFactory()
    TeamMemberFactory(user=team_owner, team=team, role="owner")
    form = CreateServiceAccountForm(
        user=team_owner,
        data={"team": team, "nickname": "Nickname"},
    )
    assert form.is_valid()
    return form.save().user


class TestUserTypes(ChoiceEnum):
    no_user = "none"
    unauthenticated = "unauthenticated"
    regular_user = "regular_user"
    deactivated_user = "deactivated_user"
    service_account = "service_account"
    superuser = "superuser"

    @classmethod
    def fake_users(cls):
        return (cls.no_user, cls.unauthenticated)

    @staticmethod
    def get_user_by_type(usertype: str):
        if usertype == TestUserTypes.no_user:
            return None
        if usertype == TestUserTypes.unauthenticated:
            return AnonymousUser()
        if usertype == TestUserTypes.regular_user:
            return UserFactory.create()
        if usertype == TestUserTypes.deactivated_user:
            return UserFactory.create(is_active=False)
        if usertype == TestUserTypes.service_account:
            return create_test_service_account_user()
        if usertype == TestUserTypes.superuser:
            return UserFactory.create(is_staff=True, is_superuser=True)
        raise AttributeError(f"Invalid useretype: {usertype}")
