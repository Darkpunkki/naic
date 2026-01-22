# NAIC Test Plan

## Overview

This document outlines a comprehensive testing strategy for the NAIC workout planning application. The plan covers unit tests, integration tests, and end-to-end tests.

## Current State

- **Existing tests:** 3 E2E tests covering basic auth and workout creation
- **Estimated coverage:** 5-10%
- **Location:** `tests/e2e/test_basic_flow.py`

---

## 1. Unit Tests

### 1.1 Models (`tests/unit/test_models.py`)

#### User Model
- [x] Create user with valid data
- [x] User password hashing works correctly
- [x] User profile fields (sex, bodyweight, gym_experience) store correctly

#### Workout Model
- [x] Create workout with required fields
- [x] Workout-user relationship works
- [x] `is_completed` default is False
- [x] Cascade delete removes associated WorkoutMovements

#### WorkoutMovement Model
- [x] Create workout-movement link
- [x] `calculate_muscle_group_impact()` returns correct structure
- [x] `calculate_muscle_group_impact()` with single muscle group (100%)
- [x] `calculate_muscle_group_impact()` with multiple muscle groups (split percentages)
- [x] `calculate_muscle_group_impact()` with bodyweight exercise
- [x] `calculate_muscle_group_impact()` with weighted exercise
- [x] `calculate_muscle_group_impact()` with multiple sets
- [x] Cascade delete removes Sets, Reps, Weights

#### Movement Model
- [x] Create movement with name
- [x] Movement-MuscleGroup relationship works

#### MuscleGroup Model
- [x] All 17 muscle groups can be created
- [x] MovementMuscleGroup stores target_percentage correctly

#### Set/Rep/Weight Models
- [x] Create set with set_order
- [x] Rep stores rep_count correctly
- [x] Weight stores weight_value and is_bodyweight flag

### 1.2 Services (`tests/unit/test_services.py`)

#### OpenAI Service (mocked)
- [x] `generate_workout_plan()` returns valid JSON structure
- [ ] `generate_workout_plan()` handles API errors gracefully (Skipped: openai_service does not handle API errors; test marked skipped.)
- [ ] `generate_workout_plan()` retries on JSON parse failure (Skipped: retry logic is in routes, not openai_service.)
- [x] `generate_weekly_workout_plan()` returns multi-day structure
- [x] `generate_movement_instructions()` returns instruction text
- [x] `generate_movement_info()` returns muscle group data
- [ ] Code fence stripping works (```json removal) (Skipped: code fence stripping is handled in routes.)

### 1.3 Utilities (`tests/unit/test_utils.py`)

#### Name Normalization
- [x] `normalize_name()` lemmatizes correctly ("Pull-Ups" -> "pull-up")
- [x] `normalize_name()` handles case variations
- [x] `normalize_name()` handles hyphenation variations

---

## 2. Integration Tests (Routes)

### 2.1 Authentication (`tests/integration/test_auth.py`)

#### Registration
- [ ] `POST /register` with valid data creates user
- [ ] `POST /register` with duplicate username fails
- [ ] `POST /register` with duplicate email fails
- [ ] `POST /register` with missing fields fails
- [ ] `POST /register` with invalid email format fails

#### Login
- [ ] `POST /login` with valid credentials succeeds
- [ ] `POST /login` with wrong password fails
- [ ] `POST /login` with non-existent user fails
- [ ] `POST /login` sets session correctly

#### Logout
- [ ] `GET /logout` clears session
- [ ] `GET /logout` redirects to login

#### Protected Routes
- [ ] All protected routes redirect to login when unauthenticated
- [ ] Protected routes: `/`, `/start_workout`, `/generate_workout`, `/stats`, etc.

### 2.2 Main Routes (`tests/integration/test_main.py`)

#### Dashboard
- [ ] `GET /` renders index with navigation buttons
- [ ] `GET /` shows user profile data

### 2.3 Workout Routes (`tests/integration/test_workouts.py`)

#### Workout Creation
- [ ] `POST /new_workout` creates workout with date
- [ ] `POST /new_workout` with invalid date format fails
- [ ] `POST /new_workout` without date fails

#### Workout Viewing
- [ ] `GET /workout/<id>` shows workout details
- [ ] `GET /workout/<id>` for non-existent workout returns 404
- [ ] `GET /workout/<id>` for another user's workout is unauthorized

#### Workout Updates
- [ ] `POST /update_workout_date/<id>` updates date
- [ ] `POST /update_workout_date/<id>` with invalid date fails
- [ ] `POST /update_workout_name/<id>` updates name
- [ ] `POST /update_workout_name/<id>` for another user's workout fails

#### Workout Deletion
- [ ] `POST /delete_workout/<id>` removes workout
- [ ] `POST /delete_workout/<id>` cascades to movements/sets
- [ ] `POST /delete_workout/<id>` for another user's workout fails

#### Workout Completion
- [ ] `POST /complete_workout/<id>` sets is_completed=True
- [ ] `POST /complete_workout/<id>` for another user's workout fails

#### Active Workout
- [ ] `GET /active_workout/<id>` renders tracking page
- [ ] `GET /active_workout/<id>` updates date to current date
- [ ] `GET /active_workout/<id>` for future-dated workout updates to today
- [ ] `GET /active_workout/<id>` for another user's workout fails

#### Start Workout
- [ ] `GET /start_workout` lists user's workouts
- [ ] `GET /start_workout` shows both completed and incomplete workouts

#### All Workouts
- [ ] `GET /all_workouts` lists all user workouts
- [ ] Filter by completed status works
- [ ] Filter by incomplete status works

#### Movement Management
- [ ] `POST /add_movement/<id>` with existing movement links it
- [ ] `POST /add_movement/<id>` with new movement creates it (mocked AI)
- [ ] `POST /add_movement/<id>` creates sets/reps/weights
- [ ] `POST /remove_movement/<id>` removes movement from workout
- [ ] `POST /remove_movement/<id>` cascades delete to sets/reps/weights

### 2.4 AI Generation Routes (`tests/integration/test_generation.py`)

> Note: All OpenAI calls should be mocked

#### Single Workout Generation
- [ ] `GET /generate_workout` renders form with user data pre-filled
- [ ] `POST /generate_workout` calls OpenAI service
- [ ] `POST /generate_workout` stores result in session
- [ ] `POST /generate_workout` redirects to confirm page

#### Workout Confirmation
- [ ] `GET /confirm_workout` displays pending workout from session
- [ ] `POST /confirm_workout` saves workout to database
- [ ] `POST /confirm_workout` creates all movements/sets/reps/weights
- [ ] `POST /confirm_workout` creates MovementMuscleGroup links
- [ ] `POST /confirm_workout` clears session data
- [ ] `GET /confirm_workout` without session data redirects

#### Weekly Workout Generation
- [ ] `GET /generate_weekly_workout` renders form
- [ ] `POST /generate_weekly_workout` generates multi-day plan
- [ ] `POST /generate_weekly_workout` stores in session

#### Weekly Workout Confirmation
- [ ] `GET /confirm_weekly_workout` displays all days
- [ ] `POST /confirm_weekly_workout` creates multiple workouts
- [ ] `POST /confirm_weekly_workout` spaces workouts 2 days apart
- [ ] `POST /confirm_weekly_workout` clears session data

### 2.5 User Routes (`tests/integration/test_user.py`)

#### Profile Updates
- [ ] `POST /update_user` updates email
- [ ] `POST /update_user` updates name
- [ ] `POST /update_user` updates bodyweight
- [ ] `POST /update_user` updates gym_experience
- [ ] `POST /update_user` with invalid data fails

#### User Data API
- [ ] `GET /user_data` returns JSON with workout history

### 2.6 Stats Routes (`tests/integration/test_stats.py`)

#### Statistics Page
- [ ] `GET /stats` renders with default time filter
- [ ] `GET /stats?time_filter=weekly` calculates weekly stats
- [ ] `GET /stats?time_filter=monthly` calculates monthly stats
- [ ] `GET /stats?time_filter=all` calculates all-time stats
- [ ] Stats show top 5 muscle group changes
- [ ] Stats compare current vs previous period correctly

#### Historical Data API
- [ ] `GET /historical_data/<muscle_group>` returns 180-day data
- [ ] `GET /historical_data/<muscle_group>` returns correct JSON format
- [ ] `GET /historical_data/<muscle_group>` for invalid muscle group handles gracefully

### 2.7 Leaderboard Routes (`tests/integration/test_leaderboard.py`)

#### Workouts Leaderboard
- [ ] `GET /leaderboard/workouts_this_week` returns ranked users
- [ ] Ranking is by workout count in last 7 days
- [ ] Users with 0 workouts are excluded or shown correctly

#### Total Impact Leaderboard
- [ ] `GET /leaderboard/total_impact_this_week` returns ranked users
- [ ] Ranking is by sum of muscle group impacts

#### Per-Muscle Leaderboard
- [ ] `GET /leaderboard/impact_per_muscle` returns pivot table
- [ ] All 17 muscle groups are columns
- [ ] Users are rows with correct impact values

#### Group Leaderboard Filtering
- [ ] Leaderboard without group_id shows all users
- [ ] Leaderboard with group_id filters to members only
- [ ] Leaderboard with invalid group_id handles gracefully
- [ ] User groups passed to template for dropdown

### 2.8 Groups Routes (`tests/integration/test_groups.py`)

#### Group Creation
- [ ] `POST /groups/create` creates group with valid data
- [ ] `POST /groups/create` sets creator as owner
- [ ] `POST /groups/create` without name fails
- [ ] `POST /groups/create` unauthenticated returns 401

#### Group Listing
- [ ] `GET /groups/my-groups` returns user's groups with roles
- [ ] `GET /groups/my-groups` includes member count
- [ ] `GET /groups/my-groups` unauthenticated returns 401

#### Leaving Groups
- [ ] `POST /groups/<id>/leave` removes membership
- [ ] Owner cannot leave without transferring/deleting
- [ ] Last member leaving deletes group
- [ ] Non-member cannot leave group they're not in

#### Invitations - Sending
- [ ] `POST /groups/<id>/invite` sends invitation to valid user
- [ ] Invite fails for non-existent user
- [ ] Invite fails for existing member
- [ ] Invite fails for pending invitation
- [ ] Non-member cannot invite to group

#### Invitations - Receiving
- [ ] `GET /groups/invitations` returns pending only
- [ ] `GET /groups/invitations` excludes accepted/declined

#### Invitations - Responding
- [ ] `POST /groups/invitations/<id>/accept` creates membership
- [ ] `POST /groups/invitations/<id>/decline` updates status
- [ ] Cannot accept/decline others' invitations
- [ ] Cannot respond to already-responded invitation

---

## 3. End-to-End Tests

### 3.1 Complete User Flows (`tests/e2e/test_flows.py`)

#### New User Onboarding
- [ ] Register -> Login -> Update Profile -> Generate First Workout -> Confirm -> View

#### Single Workout Flow
- [ ] Login -> Generate Workout -> Confirm -> Start Active Workout -> Complete

#### Weekly Plan Flow
- [ ] Login -> Generate Weekly Plan -> Confirm -> View All Workouts (multiple created)

#### Workout Execution Flow
- [ ] Login -> Select Workout -> Start Active -> (simulate tracking) -> Complete -> View Stats

#### Stats Review Flow
- [ ] Login -> Complete multiple workouts -> View Stats -> Check historical data

### 3.2 Edge Cases (`tests/e2e/test_edge_cases.py`)

#### Date Handling
- [ ] Start workout scheduled for future date -> date updates to today
- [ ] Start workout scheduled for past date -> date updates to today
- [ ] Start workout scheduled for today -> date remains today

#### Concurrent Sessions
- [ ] User logged in on multiple clients behaves correctly

#### Empty States
- [ ] New user with no workouts sees appropriate empty states
- [ ] Stats page with no data shows appropriate message
- [ ] Leaderboard with single user shows correctly

---

## 4. Security Tests

### 4.1 Authorization (`tests/security/test_authorization.py`)

- [ ] User A cannot view User B's workout
- [ ] User A cannot update User B's workout
- [ ] User A cannot delete User B's workout
- [ ] User A cannot complete User B's workout
- [ ] User A cannot access User B's active workout

### 4.2 Input Validation (`tests/security/test_validation.py`)

- [ ] SQL injection attempts in login fields
- [ ] XSS attempts in workout name
- [ ] XSS attempts in movement name
- [ ] Invalid date formats are rejected
- [ ] Extremely long inputs are handled

### 4.3 Session Security (`tests/security/test_session.py`)

- [ ] Session expires appropriately
- [ ] Session cannot be tampered with
- [ ] Logout invalidates session

---

## 5. Performance Tests (Optional)

### 5.1 Load Testing (`tests/performance/`)

- [ ] Stats calculation with 1000+ workouts
- [ ] Leaderboard with 100+ users
- [ ] Historical data query performance

---

## 6. Test Infrastructure

### 6.1 Fixtures Needed

```python
# conftest.py additions

@pytest.fixture
def authenticated_client(client):
    """Client with logged-in user"""

@pytest.fixture
def user_with_workouts(app):
    """User with sample workout data"""

@pytest.fixture
def mock_openai(monkeypatch):
    """Mocked OpenAI responses"""

@pytest.fixture
def sample_workout_json():
    """Valid workout JSON from AI"""

@pytest.fixture
def sample_weekly_plan_json():
    """Valid weekly plan JSON from AI"""
```

### 6.2 Mock Data

Create `tests/fixtures/` directory with:
- `sample_workout_response.json` - Mock OpenAI single workout response
- `sample_weekly_response.json` - Mock OpenAI weekly plan response
- `sample_movement_info.json` - Mock movement info response

### 6.3 Test Database Seeding

Create helpers in `tests/helpers.py`:
- `create_test_user()` - Create user with optional profile
- `create_test_workout()` - Create workout with movements
- `create_test_movement()` - Create movement with muscle groups
- `seed_muscle_groups()` - Seed all 17 muscle groups

---

## 7. Implementation Priority

### Phase 1: Critical Path (High Priority)
1. Authorization tests (security)
2. Workout CRUD integration tests
3. Active workout date update test
4. Model unit tests for `calculate_muscle_group_impact()`

### Phase 2: Core Features (Medium Priority)
5. AI generation tests (with mocking)
6. Stats calculation tests
7. User profile tests
8. Complete E2E flows

### Phase 3: Comprehensive Coverage (Lower Priority)
9. Leaderboard tests
10. Edge case tests
11. Input validation tests
12. Performance tests

---

## 8. Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_models.py

# Run specific test
pytest tests/e2e/test_basic_flow.py::test_register_login_and_logout_flow

# Run with verbose output
pytest tests/ -v

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/
```

---

## 9. Coverage Goals

| Category | Target Coverage |
|----------|-----------------|
| Models | 90% |
| Routes | 80% |
| Services | 85% |
| Overall | 80% |

---

## 10. Notes

- All OpenAI API calls must be mocked to avoid costs and ensure deterministic tests
- Use SQLite in-memory database for fast test execution
- Consider using `pytest-flask` for additional Flask testing utilities
- Consider using `factory_boy` for test data generation
- Tests should be independent and not rely on execution order
