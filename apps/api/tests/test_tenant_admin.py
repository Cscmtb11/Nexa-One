from app.routers.tenant_admin import GSTIN_RE, PAN_RE, STATE_CODE_RE, ALLOWED_ROLES, SETTING_KEYS


def test_gstin_format_validation():
    assert GSTIN_RE.fullmatch("01ABCDE1234F1Z5")
    assert not GSTIN_RE.fullmatch("01ABCDE1234F1Z")
    assert not GSTIN_RE.fullmatch("XXABCDE1234F1Z5")


def test_pan_format_validation():
    assert PAN_RE.fullmatch("ABCDE1234F")
    assert not PAN_RE.fullmatch("ABCDE12345")


def test_state_code_validation():
    assert STATE_CODE_RE.fullmatch("01")
    assert not STATE_CODE_RE.fullmatch("1")


def test_invitation_roles_are_limited():
    assert "member" in ALLOWED_ROLES
    assert "owner" not in ALLOWED_ROLES
    assert "platform_admin" not in ALLOWED_ROLES


def test_only_allowlisted_organisation_settings_are_supported():
    assert "currency" in SETTING_KEYS
    assert "gst_exempt" in SETTING_KEYS
    assert "jwt_secret" not in SETTING_KEYS
