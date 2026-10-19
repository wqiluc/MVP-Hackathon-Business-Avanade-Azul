from datetime import datetime, timedelta, timezone

from app.config import settings
from app.core.security import create_jwt_token
from app.services.schemas.auth_schema import LoginRequest, SessaoResponse, Usuario


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    @staticmethod
    def login(request: LoginRequest) -> SessaoResponse:
        login_id = (request.email or request.username or "").strip().lower()
        password = request.senha if request.senha is not None else request.password

        configured_accounts = (
            (
                settings.ADMIN_EMAIL.strip().lower(),
                settings.ADMIN_PASSWORD,
                "ADMIN",
                "Administrador",
                "admin",
                "u-admin",
            ),
            (
                settings.DEMO_EMAIL.strip().lower(),
                settings.DEMO_PASSWORD,
                "ANALYST",
                "Analista",
                "analista",
                "u-analista",
            ),
        )
        account = next(
            (
                configured
                for configured in configured_accounts
                if configured[0]
                and configured[1]
                and login_id == configured[0]
                and password == configured[1]
            ),
            None,
        )
        if account is None:
            raise InvalidCredentialsError(
                "Credenciais inválidas. Verifique usuário e senha."
            )

        email, _, role, name, profile, user_id = account
        token = create_jwt_token({"sub": email, "role": role})
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.ACCESS_TOKEN_EXPIRE_HOURS
        )
        return SessaoResponse(
            access_token=token,
            token_type="bearer",
            role=role,
            token=token,
            usuario=Usuario(
                id=user_id,
                nome=name,
                email=email,
                perfil=profile,
                equipe="CRM e Relacionamento",
            ),
            expiraEm=expires_at.isoformat(),
        )
