from schema.user import (
    UserAddor,
    UserUpdator,
    UserDeletor,
    UserQuery
)


class UserDomian:

    @staticmethod
    async def query(query: UserQuery):
        rows = []
        total = 0
        return rows, total
    
    @staticmethod
    async def add(addor: UserAddor):
        return 
    
    @staticmethod
    async def update(updator: UserUpdator):
        return
    
    @staticmethod
    async def delete(deletor: UserDeletor):
        return
    
    