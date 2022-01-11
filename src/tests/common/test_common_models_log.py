import pytest
from django_scopes import scope


@pytest.mark.django_db
def test_log_hides_password(submission):
    with scope(event=submission.event):
        submission.log_action(
            "test.hide", data={"password": "12345", "non-sensitive": "foo"}
        )
        log = submission.logged_actions().get(action_type="test.hide")
        assert log.json_data["password"] != "12345"
        assert log.json_data["non-sensitive"] == "foo"


@pytest.mark.django_db
def test_log_wrong_data(submission):
    with scope(event=submission.event):
        with pytest.raises(TypeError):
            submission.log_action(
                "test.hide", data=[{"password": "12345", "non-sensitive": "foo"}]
            )
