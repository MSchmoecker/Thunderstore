import ulid2
from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.authtoken.models import Token

from thunderstore.account.models import ServiceAccount
from thunderstore.core.types import UserType
from thunderstore.repository.models import (
    UploaderIdentity,
    UploaderIdentityMember,
    UploaderIdentityMemberRole,
)

User = get_user_model()


def create_service_account_username(id_: str) -> str:
    return f"{id_}.sa@thunderstore.io"


class CreateServiceAccountForm(forms.Form):
    nickname = forms.CharField(max_length=32)

    def __init__(self, user: UserType, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["identity"] = forms.ModelChoiceField(
            queryset=UploaderIdentity.objects.filter(members__user=user),
        )

    def clean_identity(self) -> UploaderIdentity:
        identity = self.cleaned_data["identity"]
        identity.ensure_can_create_service_account(self.user)
        return identity

    @transaction.atomic
    def save(self) -> ServiceAccount:
        service_account_id = ulid2.generate_ulid_as_uuid()
        username = create_service_account_username(service_account_id.hex)
        user = User.objects.create_user(
            username,
            email=username,
            first_name=self.cleaned_data["nickname"],
        )
        self.cleaned_data["identity"].add_member(
            user=user,
            role=UploaderIdentityMemberRole.member,
        )
        return ServiceAccount.objects.create(
            uuid=service_account_id,
            user=user,
            owner=self.cleaned_data["identity"],
        )


class DeleteServiceAccountForm(forms.Form):
    def __init__(self, user: UserType, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["service_account"] = forms.ModelChoiceField(
            queryset=ServiceAccount.objects.filter(owner__members__user=user),
        )

    def clean_service_account(self) -> ServiceAccount:
        service_account = self.cleaned_data["service_account"]
        service_account.owner.ensure_can_delete_service_account(self.user)
        return service_account

    def save(self) -> None:
        self.cleaned_data["service_account"].delete()


class EditServiceAccountForm(forms.Form):
    nickname = forms.CharField(max_length=32)

    def __init__(self, user: UserType, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["service_account"] = forms.ModelChoiceField(
            queryset=ServiceAccount.objects.filter(owner__members__user=user),
        )

    def clean_service_account(self) -> ServiceAccount:
        service_account = self.cleaned_data["service_account"]
        service_account.owner.ensure_can_edit_service_account(self.user)
        return service_account

    def save(self) -> ServiceAccount:
        service_account = self.cleaned_data["service_account"]
        service_account.user.first_name = self.cleaned_data["nickname"]
        service_account.user.save(update_fields=("first_name",))
        return service_account


class CreateTokenForm(forms.Form):
    def __init__(self, user: UserType, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["service_account"] = forms.ModelChoiceField(
            queryset=ServiceAccount.objects.filter(owner__members__user=user),
        )

    def clean_service_account(self) -> ServiceAccount:
        service_account = self.cleaned_data["service_account"]
        service_account.owner.ensure_can_generate_service_account_token(self.user)
        return service_account

    @transaction.atomic
    def save(self) -> Token:
        service_account_user = self.cleaned_data["service_account"].user
        Token.objects.filter(user=service_account_user).delete()
        return Token.objects.create(user=service_account_user)
