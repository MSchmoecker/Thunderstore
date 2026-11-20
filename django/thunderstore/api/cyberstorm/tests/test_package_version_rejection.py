from typing import Callable, Optional

import pytest
from rest_framework.test import APIClient

from thunderstore.community.consts import PackageListingReviewStatus
from thunderstore.community.factories import CommunityFactory, PackageListingFactory
from thunderstore.community.models import (
    CommunityMemberRole,
    CommunityMembership,
    PackageListing,
)
from thunderstore.core.factories import UserFactory
from thunderstore.core.types import UserType
from thunderstore.repository.consts import PackageVersionReviewStatus
from thunderstore.repository.factories import PackageVersionFactory, TeamMemberFactory
from thunderstore.repository.models import PackageVersion
from thunderstore.repository.models.team import TeamMemberRole

BASE_VERSION = "1.0.0"
TARGET_VERSION = "2.0.0"


def _create_listing(target_review_status: str) -> PackageListing:
    """
    An approved listing with an approved base version and a target
    version in the given review state.
    """
    listing = PackageListingFactory(
        review_status=PackageListingReviewStatus.approved,
        package_version_kwargs={
            "version_number": BASE_VERSION,
            "review_status": PackageVersionReviewStatus.approved,
        },
    )
    PackageVersionFactory(
        package=listing.package,
        name=listing.package.name,
        version_number=TARGET_VERSION,
        review_status=target_review_status,
        changelog="# Changelog",
    )
    return listing


def _get_target_version(listing: PackageListing) -> PackageVersion:
    return listing.package.versions.get(version_number=TARGET_VERSION)


def _create_viewer(kind: str, listing: PackageListing) -> Optional[UserType]:
    if kind == "anonymous":
        return None
    if kind == "superuser":
        return UserFactory(is_staff=True, is_superuser=True)

    user = UserFactory()
    if kind == "regular_user":
        pass
    elif kind == "team_member":
        TeamMemberFactory(
            team=listing.package.owner, user=user, role=TeamMemberRole.member
        )
    elif kind == "team_owner":
        TeamMemberFactory(
            team=listing.package.owner, user=user, role=TeamMemberRole.owner
        )
    elif kind in CommunityMemberRole.options():
        CommunityMembership.objects.create(
            user=user, community=listing.community, role=kind
        )
    else:
        raise ValueError(f"Unknown viewer kind: {kind}")
    return user


def _listing_version_url(listing: PackageListing, version: str) -> str:
    return (
        f"/api/cyberstorm/listing/{listing.community.identifier}/"
        f"{listing.package.namespace.name}/{listing.package.name}/v/{version}/"
    )


def _package_url(listing: PackageListing) -> str:
    return (
        f"/api/cyberstorm/package/{listing.package.namespace.name}/"
        f"{listing.package.name}/"
    )


# ---------------------------------------------------------------------------
# Listing endpoint: authenticated, so moderators may see rejected versions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("viewer", "can_view"),
    (
        ("anonymous", False),
        ("regular_user", False),
        (CommunityMemberRole.member, False),
        (CommunityMemberRole.janitor, False),
        (CommunityMemberRole.moderator, True),
        (CommunityMemberRole.owner, True),
        ("team_member", True),
        ("team_owner", True),
        ("superuser", True),
    ),
)
def test_listing_version__rejected_version_requires_manage_permission(
    api_client: APIClient,
    viewer: str,
    can_view: bool,
) -> None:
    listing = _create_listing(PackageVersionReviewStatus.rejected)
    user = _create_viewer(viewer, listing)
    if user is not None:
        api_client.force_authenticate(user)

    response = api_client.get(_listing_version_url(listing, TARGET_VERSION))

    if can_view:
        assert response.status_code == 200
        assert response.json()["full_version_name"] == (
            _get_target_version(listing).full_version_name
        )
    else:
        assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "review_status",
    (PackageVersionReviewStatus.approved, PackageVersionReviewStatus.unreviewed),
)
def test_listing_version__non_rejected_version_is_public(
    api_client: APIClient,
    review_status: str,
) -> None:
    listing = _create_listing(review_status)

    response = api_client.get(_listing_version_url(listing, TARGET_VERSION))

    assert response.status_code == 200
    assert response.json()["full_version_name"] == (
        _get_target_version(listing).full_version_name
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("review_status", "version_is_rejected"),
    (
        (PackageVersionReviewStatus.approved, False),
        (PackageVersionReviewStatus.unreviewed, False),
        (PackageVersionReviewStatus.rejected, True),
    ),
)
def test_listing_version__exposes_version_is_rejected(
    api_client: APIClient,
    review_status: str,
    version_is_rejected: bool,
) -> None:
    listing = _create_listing(review_status)
    api_client.force_authenticate(
        _create_viewer(CommunityMemberRole.moderator, listing)
    )

    response = api_client.get(_listing_version_url(listing, TARGET_VERSION))

    assert response.status_code == 200
    assert response.json()["version_is_rejected"] is version_is_rejected


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("viewer", "expected_count"),
    (
        ("anonymous", 1),
        (CommunityMemberRole.janitor, 1),
        (CommunityMemberRole.moderator, 2),
        ("team_owner", 2),
    ),
)
def test_listing__version_count_includes_rejected_only_for_moderators_and_owners(
    api_client: APIClient,
    viewer: str,
    expected_count: int,
) -> None:
    listing = _create_listing(PackageVersionReviewStatus.rejected)
    user = _create_viewer(viewer, listing)
    if user is not None:
        api_client.force_authenticate(user)

    response = api_client.get(
        f"/api/cyberstorm/listing/{listing.community.identifier}/"
        f"{listing.package.namespace.name}/{listing.package.name}/"
    )

    assert response.status_code == 200
    assert response.json()["version_count"] == expected_count


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("viewer", "can_view"),
    (
        ("anonymous", False),
        ("regular_user", False),
        ("unrelated_moderator", False),
        (CommunityMemberRole.janitor, False),
        (CommunityMemberRole.moderator, True),
        ("team_member", True),
        ("superuser", True),
    ),
)
def test_version_list__rejected_versions_require_manage_permission(
    api_client: APIClient,
    viewer: str,
    can_view: bool,
) -> None:
    listing = _create_listing(PackageVersionReviewStatus.rejected)
    if viewer == "unrelated_moderator":
        user = UserFactory()
        CommunityMembership.objects.create(
            user=user,
            community=CommunityFactory(),
            role=CommunityMemberRole.moderator,
        )
    else:
        user = _create_viewer(viewer, listing)
    if user is not None:
        api_client.force_authenticate(user)

    response = api_client.get(_package_url(listing) + "versions/")

    assert response.status_code == 200
    assert "public" not in response.get("Cache-Control", "")
    expected = {BASE_VERSION: False}
    if can_view:
        expected[TARGET_VERSION] = True
    assert {v["version_number"]: v["is_rejected"] for v in response.json()} == (
        expected
    )


@pytest.mark.django_db
def test_version_list__team_member_sees_rejected_versions_of_unlisted_package(
    api_client: APIClient,
) -> None:
    listing = _create_listing(PackageVersionReviewStatus.rejected)
    user = _create_viewer("team_member", listing)
    url = _package_url(listing) + "versions/"
    listing.delete()
    api_client.force_authenticate(user)

    response = api_client.get(url)

    assert response.status_code == 200
    assert sorted(v["version_number"] for v in response.json()) == [
        BASE_VERSION,
        TARGET_VERSION,
    ]


@pytest.mark.django_db
def test_listing_version__other_versions_stay_visible_when_one_is_rejected(
    api_client: APIClient,
) -> None:
    listing = _create_listing(PackageVersionReviewStatus.rejected)

    response = api_client.get(_listing_version_url(listing, BASE_VERSION))

    assert response.status_code == 200
    assert response.json()["full_version_name"].endswith(BASE_VERSION)


# ---------------------------------------------------------------------------
# Public (CDN cached, unauthenticated) endpoints: a rejected version must
# never be served, not even to moderators, since the response is cached
# publicly and shared between all users.
# ---------------------------------------------------------------------------


PUBLIC_VERSION_ENDPOINTS = {
    "version": "v/{version}/",
    "readme": "v/{version}/readme/",
    "changelog": "v/{version}/changelog/",
    "dependencies": "v/{version}/dependencies/",
}


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", PUBLIC_VERSION_ENDPOINTS.keys())
@pytest.mark.parametrize("viewer", ("anonymous", "team_owner", "superuser"))
@pytest.mark.parametrize(
    ("review_status", "expected_status"),
    (
        (PackageVersionReviewStatus.approved, 200),
        (PackageVersionReviewStatus.unreviewed, 200),
        (PackageVersionReviewStatus.rejected, 404),
    ),
)
def test_public_version_endpoints__rejected_version_is_hidden(
    api_client: APIClient,
    endpoint: str,
    viewer: str,
    review_status: str,
    expected_status: int,
) -> None:
    listing = _create_listing(review_status)
    user = _create_viewer(viewer, listing)
    if user is not None:
        api_client.force_authenticate(user)

    url = _package_url(listing) + PUBLIC_VERSION_ENDPOINTS[endpoint].format(
        version=TARGET_VERSION
    )
    response = api_client.get(url)

    assert response.status_code == expected_status
