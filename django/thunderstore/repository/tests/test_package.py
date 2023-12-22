from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from conftest import TestUserTypes
from thunderstore.community.factories import SiteFactory
from thunderstore.community.models.package_listing import PackageListing
from thunderstore.core.types import UserType
from thunderstore.repository.factories import PackageFactory
from thunderstore.repository.models import (
    Namespace,
    Package,
    PackageWiki,
    TeamMember,
    TeamMemberRole,
)
from thunderstore.wiki.factories import WikiPageFactory

User = get_user_model()


@pytest.mark.django_db
def test_package_get_page_url(
    active_package_listing: PackageListing,
) -> None:
    owner_url = active_package_listing.package.get_page_url(
        active_package_listing.community.identifier
    )
    assert owner_url == f"/c/test/p/Test_Team/{active_package_listing.package.name}/"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "site_host", ("thunderstore.dev", "test.thunderstore.dev", None)
)
@pytest.mark.parametrize(
    "primary_host", ("thunderstore.io", "stonderthure.io.example.org")
)
def test_package_get_full_url(
    settings: Any,
    site_host: str,
    primary_host: str,
    active_package: Package,
) -> None:
    site = SiteFactory(domain=site_host) if site_host is not None else None
    settings.PRIMARY_HOST = primary_host

    expected_host = site_host if site else primary_host
    expected_url = f"{settings.PROTOCOL}{expected_host}/package/{active_package.namespace.name}/{active_package.name}/"
    assert active_package.get_full_url(site=site) == expected_url


@pytest.mark.django_db
def test_package_deprecate() -> None:
    package: Package = PackageFactory(is_deprecated=False)
    old_updated = package.date_updated
    assert package.is_deprecated is False
    package.deprecate()
    assert package.is_deprecated is True
    assert package.date_updated == old_updated


@pytest.mark.django_db
def test_package_undeprecate() -> None:
    package: Package = PackageFactory(is_deprecated=True)
    old_updated = package.date_updated
    assert package.is_deprecated is True
    package.undeprecate()
    assert package.is_deprecated is False
    assert package.date_updated == old_updated


@pytest.mark.django_db
def test_package_deactivate() -> None:
    package = PackageFactory(is_active=True)
    old_updated = package.date_updated
    assert package.is_active is True
    package.deactivate()
    assert package.is_active is False
    assert package.date_updated == old_updated


@pytest.mark.django_db
@pytest.mark.parametrize("user_type", TestUserTypes.options())
@pytest.mark.parametrize("role", TeamMemberRole.options() + [None])
def test_package_ensure_user_can_manage_deprecation(
    namespace: Namespace, user_type: str, role: str
) -> None:
    user = TestUserTypes.get_user_by_type(user_type)
    team = namespace.team
    package = PackageFactory(owner=team, namespace=namespace)
    if role is not None and user_type not in TestUserTypes.fake_users():
        TeamMember.objects.create(user=user, team=team, role=role)

    if user_type in TestUserTypes.fake_users():
        expected_error = "Must be authenticated"
    elif user_type == TestUserTypes.deactivated_user:
        expected_error = "User has been deactivated"
    elif user_type in (TestUserTypes.site_admin, TestUserTypes.superuser):
        expected_error = None
    elif user_type == TestUserTypes.service_account:
        expected_error = "Service accounts are unable to perform this action"
    elif role in (TeamMemberRole.owner, TeamMemberRole.member):
        expected_error = None
    else:
        expected_error = "Must be a member of team to manage packages"

    if expected_error is not None:
        assert package.can_user_manage_deprecation(user) is False
        with pytest.raises(ValidationError, match=expected_error):
            package.ensure_user_can_manage_deprecation(user)
    else:
        assert package.can_user_manage_deprecation(user) is True
        assert package.ensure_user_can_manage_deprecation(user) is None


@pytest.mark.django_db
def test_package_ensure_user_can_manage_deprecation_deprecate_package_perm(
    namespace: Namespace,
    user: UserType,
):
    team = namespace.team
    package = PackageFactory(owner=team, namespace=namespace)
    user.is_staff = True
    user.save()
    assert package.can_user_manage_deprecation(user) is False
    content_type = ContentType.objects.get_for_model(Package)
    perm = Permission.objects.get(
        content_type=content_type, codename="deprecate_package"
    )
    user.user_permissions.add(perm)
    user = User.objects.get(pk=user.pk)
    assert package.can_user_manage_deprecation(user) is True


@pytest.mark.django_db
@pytest.mark.parametrize("user_type", TestUserTypes.options())
@pytest.mark.parametrize("role", TeamMemberRole.options() + [None])
def test_package_ensure_user_can_manage_wiki(
    namespace: Namespace, user_type: str, role: str
) -> None:
    user = TestUserTypes.get_user_by_type(user_type)
    team = namespace.team
    package = PackageFactory(owner=team, namespace=namespace)
    if role is not None and user_type not in TestUserTypes.fake_users():
        TeamMember.objects.create(user=user, team=team, role=role)

    if user_type in TestUserTypes.fake_users():
        expected_error = "Must be authenticated"
    elif user_type == TestUserTypes.deactivated_user:
        expected_error = "User has been deactivated"
    elif user_type == TestUserTypes.service_account:
        expected_error = "Service accounts are unable to perform this action"
    elif role in (TeamMemberRole.owner, TeamMemberRole.member):
        expected_error = None
    else:
        expected_error = "Must be a member of team to manage packages"

    if expected_error is not None:
        assert package.can_user_manage_wiki(user) is False
        with pytest.raises(ValidationError, match=expected_error):
            package.ensure_user_can_manage_wiki(user)
    else:
        assert package.can_user_manage_wiki(user) is True
        assert package.ensure_user_can_manage_wiki(user) is None


@pytest.mark.django_db
def test_package_has_wiki_no_wiki(package: Package) -> None:
    assert package.has_wiki is False


@pytest.mark.django_db
def test_package_has_wiki_no_pages(
    package: Package,
    package_wiki: PackageWiki,
) -> None:
    assert package_wiki.package == package
    assert package_wiki.wiki.pages.exists() is False
    assert package.has_wiki is False


@pytest.mark.django_db
def test_package_has_wiki_yes(
    package: Package,
    package_wiki: PackageWiki,
) -> None:
    assert package_wiki.package == package
    WikiPageFactory(wiki=package_wiki.wiki)
    assert package_wiki.wiki.pages.exists() is True
    assert package.has_wiki is True
