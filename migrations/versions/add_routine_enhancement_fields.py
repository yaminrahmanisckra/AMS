"""Add routine enhancement fields and RoutineTimeSlot table

Revision ID: routine_enhance_001
Revises: add_course_outline_cols
Create Date: 2025-01-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'routine_enhance_001'
down_revision = '30a063eccd86'
branch_labels = None
depends_on = None


def upgrade():
    # Add new fields to routine table
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('routine')]
    
    with op.batch_alter_table('routine', schema=None) as batch_op:
        # Add saved_routine_id if it doesn't exist
        if 'saved_routine_id' not in columns:
            batch_op.add_column(sa.Column('saved_routine_id', sa.Integer(), nullable=True))
            # Add foreign key constraint if possible
            try:
                batch_op.create_foreign_key('fk_routine_saved_routine', 'saved_routine', ['saved_routine_id'], ['id'])
            except Exception as e:
                # Foreign key might already exist or SQLite might not support it
                pass
        
        # Add other columns only if they don't exist
        if 'batch' not in columns:
            batch_op.add_column(sa.Column('batch', sa.String(length=20), nullable=True))
        if 'color_code' not in columns:
            batch_op.add_column(sa.Column('color_code', sa.String(length=7), nullable=True))
        if 'is_custom' not in columns:
            batch_op.add_column(sa.Column('is_custom', sa.Boolean(), nullable=True, server_default='0'))
        if 'custom_course_name' not in columns:
            batch_op.add_column(sa.Column('custom_course_name', sa.String(length=200), nullable=True))
        if 'placement_order' not in columns:
            batch_op.add_column(sa.Column('placement_order', sa.Integer(), nullable=True))
    
    # Create routine_time_slot table (check if exists first)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    if 'routine_time_slot' not in inspector.get_table_names():
        op.create_table('routine_time_slot',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('saved_routine_id', sa.Integer(), nullable=False),
            sa.Column('time_slot', sa.String(length=50), nullable=False),
            sa.Column('display_order', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['saved_routine_id'], ['saved_routine.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('saved_routine_id', 'time_slot', name='_saved_routine_time_slot_uc')
        )


def downgrade():
    # Drop routine_time_slot table
    op.drop_table('routine_time_slot')
    
    # Remove fields from routine table
    with op.batch_alter_table('routine', schema=None) as batch_op:
        batch_op.drop_column('placement_order')
        batch_op.drop_column('custom_course_name')
        batch_op.drop_column('is_custom')
        batch_op.drop_column('color_code')
        batch_op.drop_column('batch')
        # Note: saved_routine_id is kept for data integrity
