"""JWT 签发与校验，仅在本服务内验证用户身份。"""

from datetime import timedelta

import jwt
from fastapi import HTTPException
from sqlmodel import Session

from app.clock import Clock
from app.config import Config
from app.db import Database, User


class Auth:
    def __init__(self, config: Config, db: Database, clock: Clock) -> None:
        self.config, self.db, self.clock = config, db, clock

    def issue(self, user: User) -> str:
        return jwt.encode(
            {
                "sub": str(user.id),
                "iss": "deskmate",
                "aud": "deskmate-web",
                "iat": self.clock.now(),
                "exp": self.clock.now() + timedelta(minutes=self.config.jwt_expire_minutes),
            },
            self.config.jwt_secret.get_secret_value(),
            algorithm="HS256",
        )

    def resolve(self, token: str) -> User:
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret.get_secret_value(),
                algorithms=["HS256"],
                issuer="deskmate",
                audience="deskmate-web",
                options={
                    "require": ["sub", "exp", "iat"],
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
            if payload["exp"] <= self.clock.now().timestamp():
                raise ValueError("expired")
            with Session(self.db.engine) as session:
                user = session.get(User, int(payload["sub"]))
            if user is None:
                raise ValueError("unknown user")
            return user
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise HTTPException(401, "登录已过期或凭证无效") from exc
