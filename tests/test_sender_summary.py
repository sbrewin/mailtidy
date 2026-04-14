from mailtidy.mailtidy import Action, SenderSummary
import datetime
from yaml import dump, unsafe_load as load_yaml
def test_constructor():
    dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
    summary = SenderSummary(from_='someone@someplace.com', count=1, first_datetime=dt, last_datetime=dt, age=0, action=Action.NONE  )
    assert summary.from_ == 'someone@someplace.com'
    assert summary.count == 1
    assert summary.first_datetime == dt
    assert summary.last_datetime == dt
    assert summary.age == 0
    assert summary.action == Action.NONE
    assert summary.yaml_tag == '!SenderSummary'

def test_constructor_defaults():
    summary = SenderSummary('someone@someplace.com')
    assert summary.from_ == 'someone@someplace.com'
    assert summary.count == 0
    assert summary.first_datetime is None
    assert summary.last_datetime is None
    assert summary.age == 0
    assert summary.action == Action.NONE
    assert summary.yaml_tag == '!SenderSummary'

def test_yaml():
    dt = datetime.datetime(2026, 1, 1, 12, 0, 0)
    summary = SenderSummary('someone@someplace.com', first_datetime=dt, last_datetime=dt)
    yaml_str = dump(summary)
    loaded_summary = load_yaml(yaml_str)
    assert loaded_summary == summary

