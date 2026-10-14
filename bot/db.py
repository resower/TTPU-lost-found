from asgiref.sync import sync_to_async


async def db(function, *args, **kwargs):
    """Run an ordinary (sync) Django ORM function from async bot code.

    Example: user = await db(queries.get_or_create_user, tg_user)
    """
    return await sync_to_async(function)(*args, **kwargs)
