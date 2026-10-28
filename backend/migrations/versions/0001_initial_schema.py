"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-28 22:14:39.593861
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('library_folders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('path', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_scanned_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('path')
    )
    op.create_table('search_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference_image_path', sa.Text(), nullable=True),
    sa.Column('mode', sa.String(length=16), nullable=False),
    sa.Column('model_version', sa.String(length=128), nullable=True),
    sa.Column('filters', sa.JSON(), nullable=False),
    sa.Column('status', sa.Enum('queued', 'running', 'completed', 'failed', 'cancelled', name='jobstatus', native_enum=False, length=32), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('videos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('folder_id', sa.Integer(), nullable=True),
    sa.Column('path', sa.Text(), nullable=False),
    sa.Column('filename', sa.Text(), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('mtime_ns', sa.Integer(), nullable=False),
    sa.Column('file_hash', sa.String(length=64), nullable=False),
    sa.Column('duplicate_of_id', sa.Integer(), nullable=True),
    sa.Column('duration_seconds', sa.Float(), nullable=True),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('frame_rate', sa.Float(), nullable=True),
    sa.Column('codec', sa.String(length=64), nullable=True),
    sa.Column('container_format', sa.String(length=128), nullable=True),
    sa.Column('creation_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('indexing_status', sa.Enum('pending', 'indexing', 'indexed', 'failed', 'unsupported', 'missing', name='indexingstatus', native_enum=False, length=32), nullable=False),
    sa.Column('indexing_progress', sa.Float(), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['duplicate_of_id'], ['videos.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['folder_id'], ['library_folders.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('path')
    )
    with op.batch_alter_table('videos', schema=None) as batch_op:
        batch_op.create_index('ix_videos_file_hash', ['file_hash'], unique=False)
        batch_op.create_index('ix_videos_status', ['indexing_status'], unique=False)

    op.create_table('detections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('video_id', sa.Integer(), nullable=False),
    sa.Column('timestamp_seconds', sa.Float(), nullable=False),
    sa.Column('bounding_box', sa.JSON(), nullable=False),
    sa.Column('track_id', sa.Integer(), nullable=True),
    sa.Column('face_quality', sa.Float(), nullable=True),
    sa.Column('person_detection_confidence', sa.Float(), nullable=True),
    sa.Column('model_version', sa.String(length=128), nullable=False),
    sa.Column('thumbnail_path', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('detections', schema=None) as batch_op:
        batch_op.create_index('ix_detections_video_ts', ['video_id', 'timestamp_seconds'], unique=False)

    op.create_table('index_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_type', sa.Enum('scan', 'index', name='jobtype', native_enum=False, length=32), nullable=False),
    sa.Column('status', sa.Enum('queued', 'running', 'completed', 'failed', 'cancelled', name='jobstatus', native_enum=False, length=32), nullable=False),
    sa.Column('params', sa.JSON(), nullable=False),
    sa.Column('progress', sa.Float(), nullable=False),
    sa.Column('current_video_id', sa.Integer(), nullable=True),
    sa.Column('processed_frames', sa.Integer(), nullable=False),
    sa.Column('total_frames_estimate', sa.Integer(), nullable=True),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('cancel_requested', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['current_video_id'], ['videos.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('index_jobs', schema=None) as batch_op:
        batch_op.create_index('ix_index_jobs_status', ['status'], unique=False)

    op.create_table('embeddings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('detection_id', sa.Integer(), nullable=False),
    sa.Column('feature_type', sa.String(length=16), nullable=False),
    sa.Column('model_name', sa.String(length=128), nullable=False),
    sa.Column('model_version', sa.String(length=64), nullable=False),
    sa.Column('dimension', sa.Integer(), nullable=False),
    sa.Column('normalized', sa.Boolean(), nullable=False),
    sa.Column('vector', sa.LargeBinary(), nullable=True),
    sa.Column('vector_reference', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['detection_id'], ['detections.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('embeddings', schema=None) as batch_op:
        batch_op.create_index('ix_embeddings_feature_model', ['feature_type', 'model_name', 'model_version'], unique=False)

    op.create_table('search_results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('search_session_id', sa.Integer(), nullable=False),
    sa.Column('detection_id', sa.Integer(), nullable=False),
    sa.Column('face_similarity', sa.Float(), nullable=True),
    sa.Column('body_similarity', sa.Float(), nullable=True),
    sa.Column('ranking_score', sa.Float(), nullable=False),
    sa.Column('review_status', sa.Enum('unreviewed', 'confirmed', 'rejected', name='reviewstatus', native_enum=False, length=32), nullable=False),
    sa.ForeignKeyConstraint(['detection_id'], ['detections.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['search_session_id'], ['search_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('search_results', schema=None) as batch_op:
        batch_op.create_index('ix_search_results_session_rank', ['search_session_id', 'ranking_score'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('search_results', schema=None) as batch_op:
        batch_op.drop_index('ix_search_results_session_rank')

    op.drop_table('search_results')
    with op.batch_alter_table('embeddings', schema=None) as batch_op:
        batch_op.drop_index('ix_embeddings_feature_model')

    op.drop_table('embeddings')
    with op.batch_alter_table('index_jobs', schema=None) as batch_op:
        batch_op.drop_index('ix_index_jobs_status')

    op.drop_table('index_jobs')
    with op.batch_alter_table('detections', schema=None) as batch_op:
        batch_op.drop_index('ix_detections_video_ts')

    op.drop_table('detections')
    with op.batch_alter_table('videos', schema=None) as batch_op:
        batch_op.drop_index('ix_videos_status')
        batch_op.drop_index('ix_videos_file_hash')

    op.drop_table('videos')
    op.drop_table('search_sessions')
    op.drop_table('library_folders')
