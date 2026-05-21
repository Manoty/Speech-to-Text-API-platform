"""
app/cli.py

Typer CLI for production ops.
Run: python -m app.cli <command>

Commands:
    create-admin     Promote a user to admin
    list-users       List all registered users
    reset-quota      Reset a specific user's monthly quota
    purge-old-jobs   Delete failed jobs older than N days
    stats            Print platform stats to terminal
"""

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="stt-cli", help="STT Platform management CLI")
console = Console()


def get_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    engine = create_engine(settings.database_url_sync)
    return sessionmaker(bind=engine)()


@app.command()
def create_admin(
    email: str = typer.Argument(..., help="Email of user to promote"),
) -> None:
    """Promote a user to admin."""
    db = get_db()
    try:
        from app.domains.auth.models import User
        user = db.query(User).filter(User.email == email.lower()).first()
        if not user:
            console.print(f"[red]User not found: {email}[/red]")
            raise typer.Exit(1)
        user.is_admin = True
        db.commit()
        console.print(f"[green]✓ {email} is now an admin[/green]")
    finally:
        db.close()


@app.command()
def list_users(
    limit: int = typer.Option(50, help="Max users to show"),
    admins_only: bool = typer.Option(False, help="Show only admins"),
) -> None:
    """List registered users."""
    db = get_db()
    try:
        from app.domains.auth.models import User
        query = db.query(User)
        if admins_only:
            query = query.filter(User.is_admin == True)
        users = query.order_by(User.created_at.desc()).limit(limit).all()

        table = Table(title=f"Users ({len(users)})")
        table.add_column("Email", style="cyan")
        table.add_column("Active", style="green")
        table.add_column("Admin", style="yellow")
        table.add_column("Created")

        for u in users:
            table.add_row(
                u.email,
                "✓" if u.is_active else "✗",
                "✓" if u.is_admin else "✗",
                str(u.created_at.date()),
            )
        console.print(table)
    finally:
        db.close()


@app.command()
def reset_quota(
    email: str = typer.Argument(..., help="User email"),
) -> None:
    """Reset a user's monthly quota to 0."""
    db = get_db()
    try:
        from app.domains.auth.models import User
        from app.domains.quotas.models import UserQuota

        user = db.query(User).filter(User.email == email.lower()).first()
        if not user:
            console.print(f"[red]User not found: {email}[/red]")
            raise typer.Exit(1)

        quota = db.query(UserQuota).filter(UserQuota.user_id == user.id).first()
        if not quota:
            console.print(f"[yellow]No quota record for {email}[/yellow]")
            raise typer.Exit(0)

        quota.minutes_used_this_month = 0.0
        db.commit()
        console.print(f"[green]✓ Quota reset for {email}[/green]")
    finally:
        db.close()


@app.command()
def purge_old_jobs(
    days: int = typer.Option(30, help="Delete failed jobs older than N days"),
    dry_run: bool = typer.Option(True, help="Preview without deleting"),
) -> None:
    """Delete old failed transcription jobs."""
    db = get_db()
    try:
        from sqlalchemy import text
        result = db.execute(text("""
            SELECT COUNT(*) FROM transcription_jobs
            WHERE status = 'failed'
              AND created_at < NOW() - INTERVAL ':days days'
        """), {"days": days})
        count = result.scalar()

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would delete {count} failed jobs older than {days} days[/yellow]")
            return

        db.execute(text("""
            DELETE FROM transcription_jobs
            WHERE status = 'failed'
              AND created_at < NOW() - INTERVAL ':days days'
        """), {"days": days})
        db.commit()
        console.print(f"[green]✓ Deleted {count} failed jobs[/green]")
    finally:
        db.close()


@app.command()
def stats() -> None:
    """Print platform statistics."""
    db = get_db()
    try:
        from sqlalchemy import text

        result = db.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM users)                                   AS total_users,
                (SELECT COUNT(*) FROM transcription_jobs)                      AS total_jobs,
                (SELECT COUNT(*) FROM transcription_jobs WHERE status='completed') AS completed,
                (SELECT COUNT(*) FROM transcription_jobs WHERE status='failed')    AS failed,
                (SELECT COUNT(*) FROM transcription_jobs WHERE status='pending')   AS pending,
                (SELECT COALESCE(SUM(duration_seconds)/3600,0) FROM transcripts)   AS total_hours,
                (SELECT COALESCE(SUM(estimated_cost_usd),0) FROM compute_costs)    AS total_cost
        """))
        row = result.mappings().one()

        table = Table(title="Platform Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Users",       str(row["total_users"]))
        table.add_row("Total Jobs",        str(row["total_jobs"]))
        table.add_row("Completed",         str(row["completed"]))
        table.add_row("Failed",            str(row["failed"]))
        table.add_row("Pending",           str(row["pending"]))
        table.add_row("Audio Hours",       f"{float(row['total_hours']):.1f}h")
        table.add_row("Total Cost (est.)", f"${float(row['total_cost']):.4f}")

        console.print(table)
    finally:
        db.close()


if __name__ == "__main__":
    app()