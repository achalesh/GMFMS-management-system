from apps.accounts.models import Role, User, UserJurisdiction, UserRole


def user_with_role(username, role="VIEWER", scope="STATE", district="", block=""):
    user = User.objects.create_user(
        username, email=f"{username}@example.org", password="Uncommon-test-password-729!"
    )
    assign(user, role, scope, district, block)
    return user


def assign(user, role, scope, district="", block=""):
    assignment, _ = UserRole.objects.get_or_create(user=user, role=Role.objects.get(code=role))
    from apps.locations.models import Block, District, State

    state, _ = State.objects.get_or_create(code="KL", defaults={"name_en": "Kerala"})
    district_obj = block_obj = None
    if district:
        district_obj, _ = District.objects.get_or_create(
            district_code=district, defaults={"state": state, "name_en": district}
        )
    if block:
        block_obj, _ = Block.objects.get_or_create(
            block_code=block, defaults={"district": district_obj, "name_en": block}
        )
    UserJurisdiction.objects.create(
        assignment=assignment,
        scope=scope,
        district_code=district,
        block_code=block,
        district=district_obj,
        block=block_obj,
    )
    return assignment
