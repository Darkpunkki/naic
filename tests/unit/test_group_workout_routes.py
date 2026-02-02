from datetime import datetime

from app.models import (
    db,
    GroupInvitation,
    GroupJoinRequest,
    Movement,
    User,
    UserGroup,
    UserGroupMembership,
    Workout,
    WorkoutComment,
    WorkoutMovement,
)


def create_user(username):
    user = User(username=username, password_hash="x")
    db.session.add(user)
    db.session.commit()
    return user


def create_workout(user, workout_name, is_completed=True):
    workout = Workout(
        user_id=user.user_id,
        workout_name=workout_name,
        workout_date=datetime.utcnow(),
        is_completed=is_completed,
    )
    db.session.add(workout)
    db.session.flush()

    movement = Movement.query.filter_by(movement_name="Test Movement").first()
    if not movement:
        movement = Movement(movement_name="Test Movement")
        db.session.add(movement)
        db.session.flush()

    wm = WorkoutMovement(workout_id=workout.workout_id, movement_id=movement.movement_id)
    db.session.add(wm)
    db.session.commit()
    return workout


def create_group_with_members(group_name, member_roles):
    group = UserGroup(group_name=group_name, group_description="Test group")
    db.session.add(group)
    db.session.flush()

    for user, role in member_roles:
        db.session.add(UserGroupMembership(user_id=user.user_id, group_id=group.group_id, role=role))

    db.session.commit()
    return group


def set_user_session(client, user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id


def cleanup_group_related_tables():
    WorkoutComment.query.delete()
    GroupInvitation.query.delete()
    GroupJoinRequest.query.delete()
    UserGroupMembership.query.delete()
    UserGroup.query.delete()
    db.session.commit()


def test_group_workouts_requires_membership(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        cleanup_group_related_tables()
        owner = create_user("owner_member")
        outsider = create_user("outsider_user")
        group = create_group_with_members("Team One", [(owner, "owner")])
        create_workout(owner, "Owner Workout")

        set_user_session(client, outsider.user_id)
        response = client.get(f"/groups/{group.group_id}/workouts")

        assert response.status_code == 403


def test_group_workouts_list_only_group_member_workouts(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        cleanup_group_related_tables()
        owner = create_user("feed_owner")
        member = create_user("feed_member")
        outsider = create_user("feed_outsider")
        group = create_group_with_members("Team Feed", [(owner, "owner"), (member, "member")])

        create_workout(owner, "Owner Session")
        create_workout(member, "Member Session")
        create_workout(member, "Member Planned Session", is_completed=False)
        create_workout(outsider, "Outsider Session")

        set_user_session(client, owner.user_id)
        response = client.get(f"/groups/{group.group_id}/workouts")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Owner Session" in body
        assert "Member Session" in body
        assert "Member Planned Session" not in body
        assert "Outsider Session" not in body


def test_group_workout_detail_requires_visible_workout(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        cleanup_group_related_tables()
        owner = create_user("detail_owner")
        member = create_user("detail_member")
        outsider = create_user("detail_outsider")
        group = create_group_with_members("Detail Group", [(owner, "owner"), (member, "member")])

        visible_workout = create_workout(owner, "Visible Workout")
        hidden_workout = create_workout(outsider, "Hidden Workout")

        set_user_session(client, member.user_id)

        visible_response = client.get(f"/groups/{group.group_id}/workouts/{visible_workout.workout_id}")
        assert visible_response.status_code == 200
        assert "Visible Workout" in visible_response.get_data(as_text=True)

        hidden_response = client.get(f"/groups/{group.group_id}/workouts/{hidden_workout.workout_id}")
        assert hidden_response.status_code == 403


def test_group_workout_comments_crud_permissions(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        cleanup_group_related_tables()
        owner = create_user("comment_owner")
        author = create_user("comment_author")
        other_member = create_user("comment_other")

        group = create_group_with_members(
            "Comment Group",
            [(owner, "owner"), (author, "member"), (other_member, "member")],
        )
        workout = create_workout(owner, "Commented Workout")
        comments_url = f"/groups/{group.group_id}/workouts/{workout.workout_id}/comments"

        set_user_session(client, author.user_id)
        create_response = client.post(comments_url, json={"body": "Strong session!"})
        assert create_response.status_code == 201
        created_comment = create_response.get_json()["comment"]
        comment_id = created_comment["comment_id"]

        # Non-author cannot edit.
        set_user_session(client, other_member.user_id)
        edit_response = client.patch(
            f"{comments_url}/{comment_id}",
            json={"body": "Trying to edit another member's comment"},
        )
        assert edit_response.status_code == 403

        # Group owner can moderate delete.
        set_user_session(client, owner.user_id)
        delete_response = client.delete(f"{comments_url}/{comment_id}")
        assert delete_response.status_code == 200
        assert delete_response.get_json()["comment"]["is_deleted"] is True

        # All members see deleted marker.
        set_user_session(client, author.user_id)
        list_response = client.get(comments_url)
        assert list_response.status_code == 200
        payload = list_response.get_json()
        assert payload["comments"][0]["body"] == "[deleted]"


def test_group_workout_comment_validation(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        cleanup_group_related_tables()
        owner = create_user("validation_owner")
        member = create_user("validation_member")
        group = create_group_with_members("Validation Group", [(owner, "owner"), (member, "member")])
        workout = create_workout(owner, "Validation Workout")

        set_user_session(client, member.user_id)
        response = client.post(
            f"/groups/{group.group_id}/workouts/{workout.workout_id}/comments",
            json={"body": "   "},
        )
        assert response.status_code == 400
        assert "empty" in response.get_json()["error"].lower()


def test_group_workout_comments_requires_membership(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        cleanup_group_related_tables()
        owner = create_user("comments_membership_owner")
        outsider = create_user("comments_membership_outsider")
        group = create_group_with_members("Comments Membership", [(owner, "owner")])
        workout = create_workout(owner, "Comments Membership Workout")

        comments_url = f"/groups/{group.group_id}/workouts/{workout.workout_id}/comments"
        set_user_session(client, outsider.user_id)

        get_response = client.get(comments_url)
        assert get_response.status_code == 403

        post_response = client.post(comments_url, json={"body": "Should not work"})
        assert post_response.status_code == 403


def test_group_feed_redirect_uses_last_selected_group(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        cleanup_group_related_tables()
        user = create_user("group_feed_last_selected")
        first_group = create_group_with_members("First Feed Group", [(user, "member")])
        second_group = create_group_with_members("Second Feed Group", [(user, "member")])

        with client.session_transaction() as sess:
            sess['user_id'] = user.user_id
            sess['last_group_feed_group_id'] = second_group.group_id

        response = client.get("/groups/feed")
        assert response.status_code == 302
        assert response.headers["Location"].endswith(f"/groups/{second_group.group_id}/workouts")
        assert not response.headers["Location"].endswith(f"/groups/{first_group.group_id}/workouts")


def test_group_feed_redirect_accepts_group_selection(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        cleanup_group_related_tables()
        user = create_user("group_feed_selector_user")
        first_group = create_group_with_members("Selectable Feed Group", [(user, "member")])
        second_group = create_group_with_members("Fallback Feed Group", [(user, "member")])

        with client.session_transaction() as sess:
            sess['user_id'] = user.user_id
            sess['last_group_feed_group_id'] = second_group.group_id

        response = client.get(f"/groups/feed?group_id={first_group.group_id}")
        assert response.status_code == 302
        assert response.headers["Location"].endswith(f"/groups/{first_group.group_id}/workouts")

        with client.session_transaction() as sess:
            assert sess['last_group_feed_group_id'] == first_group.group_id


def test_owner_only_workout_route_unchanged(client, app):
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        owner = create_user("owner_only_owner")
        outsider = create_user("owner_only_outsider")
        workout = create_workout(owner, "Owner-only Workout")

        set_user_session(client, outsider.user_id)
        response = client.get(f"/workout/{workout.workout_id}")

        assert response.status_code == 403
