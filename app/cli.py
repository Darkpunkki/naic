"""Flask CLI commands for managing API tokens (run with FLASK_APP=run.py)."""
import click

from app.models import User
from app.services.api_token_service import ApiTokenService


def register_cli(app):
    @app.cli.group()
    def token():
        """Manage per-user API tokens."""

    @token.command("create")
    @click.argument("username")
    @click.option("--name", default="agent", help="Label for the token.")
    def create_token(username, name):
        """Mint a new API token for USERNAME (printed once)."""
        user = User.query.filter_by(username=username).first()
        if user is None:
            raise click.ClickException(f"No user named '{username}'")
        plaintext, tok = ApiTokenService.generate(user.user_id, name=name)
        click.echo(f"Token for {username} (id={tok.token_id}, name='{tok.name}'):")
        click.echo(plaintext)
        click.echo("Store it now - it will not be shown again.")

    @token.command("list")
    @click.argument("username")
    def list_tokens(username):
        """List API tokens for USERNAME."""
        user = User.query.filter_by(username=username).first()
        if user is None:
            raise click.ClickException(f"No user named '{username}'")
        tokens = ApiTokenService.list_for_user(user.user_id)
        if not tokens:
            click.echo("(no tokens)")
            return
        for t in tokens:
            status = "active" if t.is_active else "revoked"
            click.echo(f"#{t.token_id}  {t.token_prefix}...  {t.name}  {status}  last_used={t.last_used_at}")

    @token.command("revoke")
    @click.argument("token_id", type=int)
    def revoke_token(token_id):
        """Revoke a token by id."""
        ok = ApiTokenService.revoke(token_id)
        click.echo("revoked" if ok else "not found or already revoked")
