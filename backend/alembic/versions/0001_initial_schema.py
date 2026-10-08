"""initial_schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-03 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table('nodes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', spatial_index=False), nullable=False),
        sa.Column('ground_elevation_m', sa.Float(), nullable=False),
        sa.Column('invert_elevation_m', sa.Float(), nullable=False),
        sa.Column('depth_m', sa.Float(), nullable=False),
        sa.Column('has_sensor', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('pipes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('from_node', sa.String(), nullable=False),
        sa.Column('to_node', sa.String(), nullable=False),
        sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='LINESTRING', srid=4326, from_text='ST_GeomFromEWKT', name='geometry', spatial_index=False), nullable=False),
        sa.Column('length_m', sa.Float(), nullable=False),
        sa.Column('diameter_m', sa.Float(), nullable=False),
        sa.Column('slope', sa.Float(), nullable=False),
        sa.Column('manning_n', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['from_node'], ['nodes.id'], ),
        sa.ForeignKeyConstraint(['to_node'], ['nodes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('sensors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('node_id', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('installed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.CheckConstraint("type IN ('ultrasonic', 'pressure')", name='ck_sensor_type'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('detections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('storm_id', sa.String(), nullable=True),
        sa.Column('top_pipe_id', sa.String(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('candidates', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='new'),
        sa.Column('notes', sa.String(), nullable=True),
        sa.CheckConstraint('confidence >= 0 AND confidence <= 1', name='ck_detection_confidence'),
        sa.CheckConstraint("status IN ('new', 'confirmed', 'false_alarm', 'resolved')", name='ck_detection_status'),
        sa.ForeignKeyConstraint(['top_pipe_id'], ['pipes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('sim_runs',
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('blocked_pipe_id', sa.String(), nullable=True),
        sa.Column('severity', sa.Float(), nullable=True),
        sa.Column('rainfall_profile', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('dataset_path', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['blocked_pipe_id'], ['pipes.id'], ),
        sa.PrimaryKeyConstraint('run_id')
    )

    op.create_index('idx_nodes_geom', 'nodes', ['geom'], unique=False, postgresql_using='gist')
    op.create_index('idx_pipes_geom', 'pipes', ['geom'], unique=False, postgresql_using='gist')


def downgrade() -> None:
    op.drop_index('idx_pipes_geom', table_name='pipes', postgresql_using='gist')
    op.drop_index('idx_nodes_geom', table_name='nodes', postgresql_using='gist')
    op.drop_table('sim_runs')
    op.drop_table('detections')
    op.drop_table('sensors')
    op.drop_table('pipes')
    op.drop_table('nodes')
