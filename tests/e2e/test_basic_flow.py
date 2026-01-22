import json


def register_user(client, username="tester"):
    return client.post(
        "/register",
        data={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123",
        },
        follow_redirects=True,
    )


def login_user(client, username="tester", password="password123"):
    return client.post(
        "/login",
        data={
            "username": username,
            "password": password,
        },
        follow_redirects=True,
    )


def test_requires_login_redirects_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")


def test_register_login_and_logout_flow(client):
    response = register_user(client)
    assert response.status_code == 200
    assert b"Registration successful" in response.data

    response = login_user(client)
    assert response.status_code == 200
    assert b"Planner" in response.data

    response = client.get("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"Log in here" in response.data


def test_create_workout_and_view_planner(client):
    register_user(client, username="planner")
    login_user(client, username="planner")

    response = client.post(
        "/new_workout",
        data=json.dumps({"workoutDate": "2024-01-15"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["workout_id"]

    planner_response = client.get("/start_workout")
    assert planner_response.status_code == 200
    assert b"Workout Planner" in planner_response.data
    assert b"New workout" in planner_response.data
