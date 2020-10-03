import pytest

from thunderstore.community.models import PackageCategory
from thunderstore.repository.factories import PackageVersionFactory, PackageFactory
from thunderstore.repository.models import Package, UploaderIdentity, Webhook
from thunderstore.webhooks.models import WebhookType


@pytest.fixture()
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="Test",
        email="test@example.org",
        password="hunter2",
    )


@pytest.fixture()
def uploader_identity():
    return UploaderIdentity.objects.create(
        name="Test-Identity"
    )


@pytest.fixture()
def package(uploader_identity):
    return Package.objects.create(
        owner=uploader_identity,
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


@pytest.fixture()
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
def active_version(active_package):
    return active_package.versions.first()


@pytest.fixture()
def release_webhook():
    return Webhook.objects.create(
        name="test",
        webhook_url="https://example.com/",
        webhook_type=WebhookType.mod_release,
        is_active=True,
    )


@pytest.fixture()
def package_category():
    return PackageCategory.objects.create(name="Test", slug="test")
