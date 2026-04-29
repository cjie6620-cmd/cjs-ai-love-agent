from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from persistence.auth_repository import AuthRepository
from persistence.db_base import Base
from security.auth import AuthService


def _auth_service() -> AuthService:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    return AuthService(repository=AuthRepository(session_factory=session_factory))


def test_register_uses_custom_nickname_and_returns_avatar_field() -> None:
    service = _auth_service()

    user, _ = service.register(
        login_name="USER001",
        password="secret123",
        nickname="小雨",
    )
    current = service.resolve_current_user(service._issue_token_pair(user.id).access_token)

    assert user.external_user_id == "user001"
    assert current.nickname == "小雨"
    assert current.avatar_url == ""


def test_update_profile_and_avatar_persist_to_user() -> None:
    service = _auth_service()
    user, _ = service.register(login_name="user002", password="secret123")

    updated = service.update_profile(user_id=user.id, nickname="陈杰")
    with_avatar = service.update_avatar(
        user_id=user.id,
        avatar_url="/auth/avatar/avatars/avatar.png",
    )

    assert updated is not None
    assert updated.nickname == "陈杰"
    assert with_avatar is not None
    assert with_avatar.avatar_url == "/auth/avatar/avatars/avatar.png"
