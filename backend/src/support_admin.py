import argparse
import asyncio

from sqlalchemy import update

from src.database import async_session_maker
from src.models.enums import UserRole
from src.models.users import UsersORM


async def assign(email, role):
    async with async_session_maker() as session:
        result = await session.execute(
            update(UsersORM)
            .where(UsersORM.email == email)
            .values(role=UserRole(role))
            .returning(UsersORM.id)
        )
        user_id = result.scalar_one_or_none()
        if user_id is None:
            raise SystemExit(
                "Пользователь не найден. Сначала зарегистрируйте его через интерфейс."
            )
        await session.commit()
        print(
            f"Пользователь {user_id}: назначена роль {role}. Выйдите и войдите заново."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Назначение роли сотруднику поддержки")
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=["it", "admin", "kassir"], required=True)
    arguments = parser.parse_args()
    asyncio.run(assign(arguments.email, arguments.role))
