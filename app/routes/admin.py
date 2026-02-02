"""
Admin routes for managing users and groups.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from app.routes.auth import require_admin
from app.services.admin_service import AdminService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@require_admin
def dashboard():
    """Admin dashboard with overview stats."""
    stats = AdminService.get_dashboard_stats()
    return render_template('admin/dashboard.html', stats=stats)


# -------------------- User Management --------------------

@admin_bp.route('/users')
@require_admin
def list_users():
    """Paginated list of all users."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str).strip()

    pagination = AdminService.get_all_users(
        page=page,
        per_page=20,
        search=search if search else None
    )

    return render_template(
        'admin/users/list.html',
        users=pagination.items,
        pagination=pagination,
        search=search
    )


@admin_bp.route('/users/<int:user_id>')
@require_admin
def view_user(user_id):
    """Detailed user view."""
    details = AdminService.get_user_details(user_id)
    if not details:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.list_users'))

    return render_template('admin/users/view.html', **details)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@require_admin
def edit_user(user_id):
    """Edit user details."""
    details = AdminService.get_user_details(user_id)
    if not details:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.list_users'))

    if request.method == 'POST':
        data = {
            'username': request.form.get('username', '').strip(),
            'email': request.form.get('email', '').strip(),
            'first_name': request.form.get('first_name', '').strip() or None,
            'last_name': request.form.get('last_name', '').strip() or None,
            'sex': request.form.get('sex', '').strip() or None,
            'bodyweight': request.form.get('bodyweight', '').strip() or None,
            'gym_experience': request.form.get('gym_experience', '').strip() or None,
            'workout_goal': request.form.get('workout_goal', '').strip() or None
        }

        # Convert bodyweight to decimal if provided
        if data['bodyweight']:
            try:
                data['bodyweight'] = float(data['bodyweight'])
            except ValueError:
                flash('Invalid bodyweight value.', 'danger')
                return render_template('admin/users/edit.html', **details)

        admin_id = session['user_id']
        success, message = AdminService.update_user(admin_id, user_id, data)

        if success:
            flash(message, 'success')
            return redirect(url_for('admin.view_user', user_id=user_id))
        else:
            flash(message, 'danger')

    return render_template('admin/users/edit.html', **details)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@require_admin
def delete_user(user_id):
    """Delete user with confirmation."""
    admin_id = session['user_id']
    success, message = AdminService.delete_user(admin_id, user_id)

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('admin.list_users'))


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@require_admin
def toggle_admin(user_id):
    """Grant/revoke admin status."""
    admin_id = session['user_id']
    success, message = AdminService.toggle_admin(admin_id, user_id)

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('admin.view_user', user_id=user_id))


# -------------------- Group Management --------------------

@admin_bp.route('/groups')
@require_admin
def list_groups():
    """Paginated list of all groups."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str).strip()

    pagination = AdminService.get_all_groups(
        page=page,
        per_page=20,
        search=search if search else None
    )

    return render_template(
        'admin/groups/list.html',
        groups=pagination.items,
        pagination=pagination,
        search=search
    )


@admin_bp.route('/groups/<int:group_id>')
@require_admin
def view_group(group_id):
    """Detailed group view."""
    details = AdminService.get_group_details(group_id)
    if not details:
        flash('Group not found.', 'danger')
        return redirect(url_for('admin.list_groups'))

    return render_template('admin/groups/view.html', **details)


@admin_bp.route('/groups/<int:group_id>/edit', methods=['GET', 'POST'])
@require_admin
def edit_group(group_id):
    """Edit group details."""
    details = AdminService.get_group_details(group_id)
    if not details:
        flash('Group not found.', 'danger')
        return redirect(url_for('admin.list_groups'))

    if request.method == 'POST':
        data = {
            'group_name': request.form.get('group_name', '').strip(),
            'group_description': request.form.get('group_description', '').strip() or None
        }

        if not data['group_name']:
            flash('Group name is required.', 'danger')
            return render_template('admin/groups/edit.html', **details)

        admin_id = session['user_id']
        success, message = AdminService.update_group(admin_id, group_id, data)

        if success:
            flash(message, 'success')
            return redirect(url_for('admin.view_group', group_id=group_id))
        else:
            flash(message, 'danger')

    return render_template('admin/groups/edit.html', **details)


@admin_bp.route('/groups/<int:group_id>/delete', methods=['POST'])
@require_admin
def delete_group(group_id):
    """Delete group with confirmation."""
    admin_id = session['user_id']
    success, message = AdminService.delete_group(admin_id, group_id)

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('admin.list_groups'))


# -------------------- Audit Logs --------------------

@admin_bp.route('/logs')
@require_admin
def audit_logs():
    """View audit log history."""
    page = request.args.get('page', 1, type=int)
    admin_filter = request.args.get('admin_id', type=int)
    action_filter = request.args.get('action', '', type=str).strip() or None
    target_filter = request.args.get('target_type', '', type=str).strip() or None

    pagination = AdminService.get_audit_logs(
        page=page,
        per_page=50,
        admin_id=admin_filter,
        action=action_filter,
        target_type=target_filter
    )

    return render_template(
        'admin/logs.html',
        logs=pagination.items,
        pagination=pagination,
        admin_filter=admin_filter,
        action_filter=action_filter,
        target_filter=target_filter
    )
