import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from thunderstore.account.factories import ServiceAccountFactory
from thunderstore.core.types import UserType
from thunderstore.repository.factories import TeamFactory, TeamMemberFactory
from thunderstore.repository.models.team import Team

User = get_user_model()


@pytest.mark.django_db
def test_team_detail_api_view__for_active_team__returns_data(
    api_client: APIClient,
    team: Team,
):
    response = api_client.get(f"/api/cyberstorm/team/{team.name}/")
    result = response.json()

    assert response.status_code == 200
    assert team.name == result["name"]
    assert team.donation_link == result["donation_link"]


@pytest.mark.django_db
def test_team_detail_api_view__for_nonexisting_team__returns_404(api_client: APIClient):
    response = api_client.get("/api/cyberstorm/team/bad/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_team_detail_api_view__when_fetching_team__is_case_insensitive(
    api_client: APIClient,
):
    TeamFactory(name="RaDTeAm")

    response = api_client.get("/api/cyberstorm/team/radteam/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_team_detail_api_view__for_inactive_team__returns_404(
    api_client: APIClient,
    team: Team,
):
    team.is_active = False
    team.save()

    response = api_client.get(f"/api/cyberstorm/team/{team.name}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_team_membership_permission__for_unauthenticated_user__returns_401(
    api_client: APIClient,
    team: Team,
):
    response = api_client.get(f"/api/cyberstorm/team/{team.name}/members/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_team_membership_permission__for_nonexisting_team__returns_404(
    api_client: APIClient,
    user: UserType,
):
    api_client.force_authenticate(user)

    response = api_client.get("/api/cyberstorm/team/bad/members/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_team_membership_permission__for_inactive_team__returns_404(
    api_client: APIClient,
    team: Team,
    user: UserType,
):
    team.is_active = False
    team.save()
    api_client.force_authenticate(user)

    response = api_client.get(f"/api/cyberstorm/team/{team.name}/members/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_team_membership_permission__for_nonmember__returns_403(
    api_client: APIClient,
    team: Team,
    user: UserType,
):
    api_client.force_authenticate(user)

    response = api_client.get(f"/api/cyberstorm/team/{team.name}/members/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_team_membership_permission__for_member__returns_200(
    api_client: APIClient,
    team: Team,
    user: UserType,
):
    TeamMemberFactory(team=team, user=user)
    api_client.force_authenticate(user)

    response = api_client.get(f"/api/cyberstorm/team/{team.name}/members/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_team_membership_permission__when_fetching_team__is_case_insensitive(
    api_client: APIClient,
    team: Team,
    user: UserType,
):
    team = TeamFactory(name="ThunderGods")
    TeamMemberFactory(team=team, user=user)
    api_client.force_authenticate(user)

    response = api_client.get("/api/cyberstorm/team/thundergods/members/")

    assert response.status_code == 200


@pytest.mark.django_db
def test_team_members_api_view__for_member__returns_only_real_users(
    api_client: APIClient,
    team: Team,
    user: UserType,
):
    TeamMemberFactory(team=team, user=user, role="member")
    ServiceAccountFactory(owner=team)
    api_client.force_authenticate(user)

    response = api_client.get(f"/api/cyberstorm/team/{team.name}/members/")
    result = response.json()

    assert len(result) == 1
    assert result[0]["identifier"] == user.id
    assert result[0]["username"] == user.username
    assert result[0]["avatar"] is None
    assert result[0]["role"] == "member"


@pytest.mark.django_db
def test_team_members_api_view__for_member__sorts_results(
    api_client: APIClient,
    team: Team,
):
    alice = User.objects.create(username="Alice")
    bob = User.objects.create(username="Bob")
    erin = User.objects.create(username="Erin")
    dan = User.objects.create(username="Dan")
    charlie = User.objects.create(username="Charlie")
    TeamMemberFactory(team=team, user=alice, role="member")
    TeamMemberFactory(team=team, user=bob, role="owner")
    TeamMemberFactory(team=team, user=erin, role="member")
    TeamMemberFactory(team=team, user=dan, role="owner")
    TeamMemberFactory(team=team, user=charlie, role="member")
    api_client.force_authenticate(alice)

    response = api_client.get(f"/api/cyberstorm/team/{team.name}/members/")
    result = response.json()

    # Owners alphabetically, then members alphabetically.
    assert len(result) == 5
    assert result[0]["username"] == bob.username
    assert result[1]["username"] == dan.username
    assert result[2]["username"] == alice.username
    assert result[3]["username"] == charlie.username
    assert result[4]["username"] == erin.username


@pytest.mark.django_db
def test_team_service_accounts_api_view__for_member__returns_only_service_accounts(
    api_client: APIClient,
    team: Team,
    user: UserType,
):
    TeamMemberFactory(team=team, user=user, role="member")
    sa = ServiceAccountFactory(owner=team)
    api_client.force_authenticate(user)

    response = api_client.get(f"/api/cyberstorm/team/{team.name}/service-accounts/")
    result = response.json()

    assert len(result) == 1
    assert result[0]["identifier"] == str(sa.uuid)
    assert result[0]["name"] == sa.user.first_name
    assert result[0]["last_used"] is None


@pytest.mark.django_db
def test_team_service_accounts_api_view__for_member__sorts_results(
    api_client: APIClient,
    team: Team,
    user: UserType,
):
    bob = User.objects.create(username="Bob", first_name="Bob")
    charlie = User.objects.create(username="Charlie", first_name="Charlie")
    alice = User.objects.create(username="Alice", first_name="Alice")
    ServiceAccountFactory(owner=team, user=bob)
    ServiceAccountFactory(owner=team, user=charlie)
    ServiceAccountFactory(owner=team, user=alice)
    TeamMemberFactory(team=team, user=user, role="member")
    api_client.force_authenticate(user)

    response = api_client.get(f"/api/cyberstorm/team/{team.name}/service-accounts/")
    result = response.json()

    assert len(result) == 3
    assert result[0]["name"] == alice.first_name
    assert result[1]["name"] == bob.first_name
    assert result[2]["name"] == charlie.first_name
