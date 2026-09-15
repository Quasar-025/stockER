import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import settings
from app.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Dynamically set the database URL from settings
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

def include_object(object, name, type_, reflected, compare_to):
    """Filter out TimescaleDB internal tables from autogenerate."""
    if type_ == "table" and name.startswith("_timescaledb"):
        return False
    return True

def process_revision_directives(context, revision, directives):
    """Add TimescaleDB hypertable creation after table creation."""
    script = directives[0]
    
    # We want to check if the 'ohlcv' table is being created in this migration
    has_ohlcv_creation = False
    
    # Simple check - this would typically be more robust in a real app
    # but for bootstrap purposes we can just look at the table names in the upgrade ops
    for op in getattr(script.upgrade_ops, "ops", []):
        if getattr(op, "__class__", None).__name__ == "CreateTableOp":
            if getattr(op, "table_name", "") == "ohlcv":
                has_ohlcv_creation = True
                
    if has_ohlcv_creation:
        # Add hypertable creation after the table is created
        from alembic.operations import ops
        
        # We need to manually add the raw SQL to create the hypertable
        hypertable_sql = ops.ExecuteSQLOp(
            "SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE);"
        )
        script.upgrade_ops.ops.append(hypertable_sql)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection, 
        target_metadata=target_metadata,
        include_object=include_object,
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
