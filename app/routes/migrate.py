"""
Temporary migration endpoint for running database migrations on Render free tier.
DELETE THIS FILE after migration is complete!
"""
from flask import Blueprint, jsonify, request
from app.models import db
from sqlalchemy import text
import os

migrate_bp = Blueprint('migrate', __name__)

# Secret token to prevent unauthorized access
MIGRATION_SECRET = os.getenv('MIGRATION_SECRET', 'change-me-in-production')

@migrate_bp.route('/run-migration-add-group-join-requests', methods=['GET'])
def run_migration():
    """
    Run the GroupJoinRequests table migration.
    Access: /run-migration-add-group-join-requests?secret=YOUR_SECRET
    """
    # Check secret token
    provided_secret = request.args.get('secret', '')
    if provided_secret != MIGRATION_SECRET:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Check if table already exists
        inspector = db.inspect(db.engine)
        if 'groupjoinrequests' in [t.lower() for t in inspector.get_table_names()]:
            return jsonify({
                'success': True,
                'message': 'GroupJoinRequests table already exists. No migration needed.'
            })

        # Create the table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS GroupJoinRequests (
            request_id SERIAL PRIMARY KEY,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            responded_at TIMESTAMP DEFAULT NULL,
            responded_by INTEGER DEFAULT NULL,
            FOREIGN KEY (group_id) REFERENCES UserGroups(group_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (responded_by) REFERENCES Users(user_id) ON DELETE SET NULL
        );
        """

        # Create indexes
        create_indexes_sql = """
        CREATE INDEX IF NOT EXISTS idx_group_status ON GroupJoinRequests(group_id, status);
        CREATE INDEX IF NOT EXISTS idx_user_status ON GroupJoinRequests(user_id, status);
        """

        db.session.execute(text(create_table_sql))
        db.session.execute(text(create_indexes_sql))
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'GroupJoinRequests table created successfully!',
            'table_structure': {
                'request_id': 'Primary key',
                'group_id': 'Foreign key to UserGroups',
                'user_id': 'User requesting to join',
                'status': 'pending/accepted/rejected',
                'created_at': 'When request was made',
                'responded_at': 'When request was accepted/rejected',
                'responded_by': 'Admin/owner who responded'
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
