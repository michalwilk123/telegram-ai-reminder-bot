import pytest

from managers.storage_manager import StorageManager, rotate_messages


@pytest.fixture
async def storage_manager():
    manager = StorageManager('sqlite+aiosqlite:///:memory:')
    await manager.init_db()
    yield manager
    await manager.close()


def test_rotate_messages_with_fewer_than_max():
    messages = [{'id': 1}, {'id': 2}, {'id': 3}]
    result = rotate_messages(messages, max_messages=5)
    assert result == [{'id': 1}, {'id': 2}, {'id': 3}]
    assert len(result) == 3


def test_rotate_messages_with_exactly_max():
    messages = [{'id': 1}, {'id': 2}, {'id': 3}]
    result = rotate_messages(messages, max_messages=3)
    assert result == [{'id': 1}, {'id': 2}, {'id': 3}]
    assert len(result) == 3


def test_rotate_messages_with_more_than_max():
    messages = [{'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}, {'id': 5}]
    result = rotate_messages(messages, max_messages=3)
    assert result == [{'id': 3}, {'id': 4}, {'id': 5}]
    assert len(result) == 3


def test_rotate_messages_with_zero_max_raises_error():
    messages = [{'id': 1}, {'id': 2}]
    with pytest.raises(ValueError, match='max_messages must be positive'):
        rotate_messages(messages, max_messages=0)


def test_rotate_messages_with_negative_max_raises_error():
    messages = [{'id': 1}, {'id': 2}]
    with pytest.raises(ValueError, match='max_messages must be positive'):
        rotate_messages(messages, max_messages=-1)


def test_rotate_messages_with_empty_list():
    messages = []
    result = rotate_messages(messages, max_messages=5)
    assert result == []


@pytest.mark.asyncio
async def test_user_token_flow(storage_manager):
    telegram_id = 123456
    token_data = {'access_token': 'abc', 'refresh_token': 'def'}

    # Test saving token
    await storage_manager.save_user_token(telegram_id, token_data)

    # Test retrieving token
    saved_data = await storage_manager.get_user_token(telegram_id)
    assert saved_data == token_data

    # Test updating token
    new_token_data = {'access_token': 'xyz', 'refresh_token': 'def'}
    await storage_manager.save_user_token(telegram_id, new_token_data)

    updated_data = await storage_manager.get_user_token(telegram_id)
    assert updated_data == new_token_data

    # Test retrieving non-existent token
    assert await storage_manager.get_user_token(999999) is None


@pytest.mark.asyncio
async def test_reminder_flow(storage_manager):
    user_id = '123456'
    cron = '* * * * *'
    message = 'Test Reminder'

    # Test adding reminder
    reminder_id = await storage_manager.add_reminder(user_id, cron, message)
    assert isinstance(reminder_id, int)

    # Test getting reminders for user
    reminders = await storage_manager.get_reminders(user_id)
    assert len(reminders) == 1
    assert reminders[0]['id'] == reminder_id
    assert reminders[0]['user_id'] == user_id
    assert reminders[0]['cron'] == cron
    assert reminders[0]['message'] == message

    # Test getting all reminders
    all_reminders = await storage_manager.get_all_reminders()
    assert len(all_reminders) == 1

    # Test deleting reminder
    deleted = await storage_manager.delete_reminder(reminder_id)
    assert deleted is True

    reminders = await storage_manager.get_reminders(user_id)
    assert len(reminders) == 0

    # Test deleting non-existent reminder
    deleted = await storage_manager.delete_reminder(999)
    assert deleted is False


@pytest.mark.asyncio
async def test_conversation_history_rotation(storage_manager):
    user_id = '12345'

    messages = [
        {'role': 'user', 'content': 'msg1'},
        {'role': 'assistant', 'content': 'msg2'},
        {'role': 'user', 'content': 'msg3'},
    ]
    await storage_manager.save_conversation_history(user_id, messages, max_messages=5)

    saved = await storage_manager.get_conversation_history(user_id)
    assert len(saved) == 3
    assert saved == messages

    more_messages = [
        {'role': 'user', 'content': 'msg1'},
        {'role': 'assistant', 'content': 'msg2'},
        {'role': 'user', 'content': 'msg3'},
        {'role': 'assistant', 'content': 'msg4'},
        {'role': 'user', 'content': 'msg5'},
        {'role': 'assistant', 'content': 'msg6'},
        {'role': 'user', 'content': 'msg7'},
    ]
    await storage_manager.save_conversation_history(user_id, more_messages, max_messages=5)

    saved = await storage_manager.get_conversation_history(user_id)
    assert len(saved) == 5
    assert saved == [
        {'role': 'user', 'content': 'msg3'},
        {'role': 'assistant', 'content': 'msg4'},
        {'role': 'user', 'content': 'msg5'},
        {'role': 'assistant', 'content': 'msg6'},
        {'role': 'user', 'content': 'msg7'},
    ]


@pytest.mark.asyncio
async def test_conversation_history_empty(storage_manager):
    user_id = '99999'
    history = await storage_manager.get_conversation_history(user_id)
    assert history == []
