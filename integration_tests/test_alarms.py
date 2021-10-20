# Copyright (c) 2020 Software AG,
# Darmstadt, Germany and/or Software AG USA Inc., Reston, VA, USA,
# and/or its subsidiaries and/or its affiliates and/or their licensors.
# Use, reproduction, transfer, publication or disclosure is prohibited except
# as specifically provided for in your License Agreement with Software AG.

# pylint: disable=redefined-outer-name

from __future__ import annotations

from typing import List

import pytest

from c8y_api import CumulocityApi
from c8y_api.model import Device, Alarm

from tests import RandomNameGenerator


def test_CRUD(live_c8y: CumulocityApi, sample_device: Device):  # noqa (case)
    """Verify that basic CRUD functionality works."""

    typename = RandomNameGenerator.random_name()
    alarm = Alarm(c8y=live_c8y, type=typename, text=f'{typename} text', source=sample_device.id,
                  severity=Alarm.Severity.MAJOR)

    created_alarm = alarm.create()
    try:
        # 1) assert correct creation
        assert created_alarm.id
        assert created_alarm.type == typename
        assert typename in created_alarm.text
        assert created_alarm.status == Alarm.Status.ACTIVE  # auto generated by Cumulocity
        assert created_alarm.count  # auto generated by Cumulocity
        assert created_alarm.time  # auto generated by API
        assert created_alarm.creation_time  # auto generated by Cumulocity

        # 2) update updatable fields
        created_alarm.text = f'{typename} updated'
        created_alarm.severity = Alarm.Severity.MINOR
        created_alarm.status = Alarm.Status.ACKNOWLEDGED

        updated_alarm = created_alarm.update()
        # -> text should be updated in db
        assert updated_alarm.text == created_alarm.text
        assert updated_alarm.status == created_alarm.status
        assert updated_alarm.severity == created_alarm.severity

        # 3) use apply_to
        model_alarm = Alarm(c8y=live_c8y, text='some text', custom_attribute='value')
        model_alarm.apply_to(created_alarm.id)
        # -> text should be updated in db
        updated_alarm = live_c8y.alarms.get(created_alarm.id)
        assert updated_alarm.text == 'some text'
        assert updated_alarm.custom_attribute == 'value'

    finally:
        created_alarm.delete()

    # 4) assert deletion
    with pytest.raises(KeyError) as e:
        live_c8y.alarms.get(created_alarm.id)
        assert created_alarm.id in str(e)


def test_CRUD_2(live_c8y: CumulocityApi, sample_device: Device):  # noqa (case)
    """Verify that basic CRUD functionality via the API works."""

    typename = RandomNameGenerator.random_name()
    time = '1970-01-01T11:22:33Z'
    alarm1 = Alarm(c8y=live_c8y, type=typename + '_1', text=f'{typename} text', source=sample_device.id,
                   time=time, severity=Alarm.Severity.MINOR)
    alarm2 = Alarm(c8y=live_c8y, type=typename + '_2', text=f'{typename} text', source=sample_device.id,
                   time=time, severity=Alarm.Severity.MINOR)

    # 1) create multiple events and read from Cumulocity
    live_c8y.alarms.create(alarm1, alarm2)
    get_filter = {'source': sample_device.id,
                  'before': '1970-01-02',
                  'after': '1970-01-01'}

    # -> we should have exactly 2 alarms of this type
    alarms = live_c8y.alarms.get_all(**get_filter)
    alarm_ids = [e.id for e in alarms]
    assert len(alarms) == 2

    try:
        # 2) update updatable fields
        for alarm in alarms:
            alarm.text = 'new text'
            alarm.severity = Alarm.Severity.MAJOR
            alarm.status = Alarm.Status.ACKNOWLEDGED
        live_c8y.alarms.update(*alarms)

        # -> still just 2 alarms, but with updated fields
        alarms = live_c8y.alarms.get_all(**get_filter)
        assert len(alarms) == 2
        for alarm in alarms:
            assert alarm.text == 'new text'
            assert alarm.severity == Alarm.Severity.MAJOR
            assert alarm.status == Alarm.Status.ACKNOWLEDGED

        # 5) apply mode updates
        model = Alarm(text='another update', simple_attribute='value')
        live_c8y.alarms.apply_to(model, *alarm_ids)

        # -> the new text should be in all events
        alarms = live_c8y.alarms.get_all(**get_filter)
        assert len(alarms) == 2
        assert all(a.text == 'another update' for a in alarms)
        assert all(a.simple_attribute == 'value' for a in alarms)

    finally:
        live_c8y.alarms.delete_by(**get_filter)

    # 6) assert deletion
    assert not live_c8y.alarms.get_all(**get_filter)


@pytest.fixture(scope='session')
def sample_alarms(factory, sample_device) -> List[Alarm]:
    """Provide a set of sample Alarm instances that will automatically
    be removed after the test function."""
    typename = RandomNameGenerator.random_name()
    result = []
    for i in range(1, 6):
        alarm = Alarm(type=f'{typename}_{i}', text=f'{typename} text', source=sample_device.id,
                      time='2020-12-31T11:33:55Z', severity=Alarm.Severity.WARNING)
        result.append(factory(alarm))
    return result


def test_apply_by(live_c8y: CumulocityApi, sample_alarms: List[Alarm]):
    """Verify that the count function works."""
    alarm = sample_alarms[0]
    model = Alarm(status=Alarm.Status.ACKNOWLEDGED)

    filter_kwargs = {'source': alarm.source,
                     'severity': alarm.severity,
                     'before': '2021-01-01',
                     'after': '2020-12-31'}

    # 1) apply model change by query
    live_c8y.alarms.apply_by(model, **filter_kwargs)

    # -> all matching objects should have been updated
    alarms = live_c8y.alarms.get_all(**filter_kwargs)
    assert all(a.status == model.status for a in alarms)


def test_count(live_c8y: CumulocityApi, sample_alarms: List[Alarm]):
    """Verify that the count function works."""
    alarm = sample_alarms[0]
    count = live_c8y.alarms.count(source=alarm.source, severity=alarm.severity,
                                  before='2021-01-01', after='2020-12-31')
    assert count == len(sample_alarms)
