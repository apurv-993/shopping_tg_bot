from database import (
    initialize_database,
    add_user,
    get_user,
    can_search,
    record_search,
    is_premium
)


initialize_database()

user_id = 123456789

add_user(
    user_id,
    "test_user",
    "Test User"
)

print("User:")
print(get_user(user_id))

print("\nPremium:")
print(is_premium(user_id))

print("\nCan search:")
print(can_search(user_id))

record_search(user_id)

print("\nAfter one search:")
print(get_user(user_id))