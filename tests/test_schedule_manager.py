from unittest.mock import AsyncMock, MagicMock

from apscheduler.triggers.cron import CronTrigger
import pytest

from managers.schedule_manager import ScheduleManager


@pytest.fixture
def schedule_manager():
    manager = ScheduleManager()
    # Mock the internal scheduler to avoid actual job scheduling logic dependencies
    manager.scheduler = MagicMock()
    return manager


@pytest.mark.asyncio
async def test_add_reminder_valid(schedule_manager):
    reminder_id = 1
    user_id = 123
    cron = '* * * * *'
    message = 'hello'

    await schedule_manager.add_reminder(reminder_id, user_id, cron, message)

    # Verify scheduler.add_job was called correctly
    schedule_manager.scheduler.add_job.assert_called_once()
    call_args = schedule_manager.scheduler.add_job.call_args
    _, kwargs = call_args

    assert kwargs['id'] == str(reminder_id)
    assert isinstance(kwargs['trigger'], CronTrigger)
    assert kwargs['args'] == [user_id, message]
    assert kwargs['replace_existing'] is True


@pytest.mark.asyncio
async def test_add_reminder_invalid_cron(schedule_manager):
    reminder_id = 1
    user_id = 123
    cron = 'invalid cron'
    message = 'hello'

    with pytest.raises(ValueError, match='Invalid cron expression'):
        await schedule_manager.add_reminder(reminder_id, user_id, cron, message)


@pytest.mark.asyncio
async def test_delete_reminder(schedule_manager):
    reminder_id = 1

    # Setup mock to simulate job existing
    schedule_manager.scheduler.get_job.return_value = True

    result = await schedule_manager.delete_reminder(reminder_id)
    assert result is True
    schedule_manager.scheduler.remove_job.assert_called_with(str(reminder_id))

    # Setup mock to simulate job not existing
    schedule_manager.scheduler.get_job.return_value = None
    result = await schedule_manager.delete_reminder(2)
    assert result is False


@pytest.mark.asyncio
async def test_callback_execution():
    manager = ScheduleManager()
    callback = AsyncMock()
    manager.set_callback(callback)

    user_id = 123
    message = 'test message'

    await manager._job_wrapper(user_id, message)
    callback.assert_awaited_with(user_id, message)

    # Test error handling in callback (should not raise exception)
    callback.side_effect = Exception('Callback Error')
    await manager._job_wrapper(user_id, message)


@pytest.mark.asyncio
async def test_start_loads_reminders():
    # Mock on_start callback
    initial_reminders = [
        {'id': 1, 'user_id': 101, 'cron': '* * * * *', 'message': 'msg1'},
        {'id': 2, 'user_id': 102, 'cron': '0 12 * * *', 'message': 'msg2'},
    ]
    on_start = AsyncMock(return_value=initial_reminders)

    manager = ScheduleManager(on_start=on_start)
    manager.scheduler = MagicMock()
    manager.scheduler.running = False

    await manager.start()

    on_start.assert_awaited_once()
    assert manager.scheduler.add_job.call_count == 2
    manager.scheduler.start.assert_called_once()
