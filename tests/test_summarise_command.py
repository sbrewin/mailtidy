from mailtidy.mailtidy import Action, MailboxManager, SummaryCommand
from yaml import unsafe_load as load_yaml

def test_summary_command(imap_connection_data, mock_mailbox, mock_mails,  tmp_path):
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    summaries_path = tmp_path / "summaries.yml"
    summary_command = SummaryCommand(manager=manager, output_file=str(summaries_path), unique=False)
    rc = summary_command.execute()
    assert rc == 0
    # Parse the output file and check that it contains the expected summaries
    with open(summaries_path, mode="rt", encoding="utf-8") as file:
        summaries = load_yaml(file)
    assert len(summaries) == 2 # We expect 2 summaries, one for the first two mails from the same sender, and one for the third mail from a different sender
    # TODO Make these tests less brittle by not relying on the order of the summaries in the output file. There order is not guaranteed, and it may change if the implementation changes. Instead, we should check that the summaries contain the expected data regardless of their order in the output file.
    assert summaries[0].from_ == mock_mails[2].from_.split("@")[-1]
    assert summaries[0].count == 1
    assert summaries[0].first_datetime == mock_mails[2].date
    assert summaries[0].last_datetime == mock_mails[2].date
    assert summaries[0].age == 0
    assert summaries[0].action == Action.NONE
    assert summaries[1].from_ == mock_mails[1].from_.split("@")[-1]
    assert summaries[1].count == 2
    assert summaries[1].first_datetime == mock_mails[0].date
    assert summaries[1].last_datetime == mock_mails[1].date
    assert summaries[1].age == 0
    assert summaries[1].action == Action.NONE

def test_summary_command_unique(imap_connection_data, mock_mailbox, mock_mails,  tmp_path):
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    summaries_path = tmp_path / "summaries.yml"
    summary_command = SummaryCommand(manager=manager, output_file=str(summaries_path), unique=True)
    rc = summary_command.execute()
    assert rc == 0
    # Parse the output file and check that it contains the expected summaries
    with open(summaries_path, mode="rt", encoding="utf-8") as file:
        summaries = load_yaml(file)
    assert len(summaries) == 2 # We expect 2 summaries, one for the first two mails from the same sender, and one for the third mail from a different sender
    # TODO Make these tests less brittle by not relying on the order of the summaries in the output file. There order is not guaranteed, and it may change if the implementation changes. Instead, we should check that the summaries contain the expected data regardless of their order in the output file.
    assert summaries[0].from_ == mock_mails[2].from_
    assert summaries[0].count == 1
    assert summaries[0].first_datetime == mock_mails[2].date
    assert summaries[0].last_datetime == mock_mails[2].date
    assert summaries[0].age == 0
    assert summaries[0].action == Action.NONE
    assert summaries[1].from_ == mock_mails[0].from_
    assert summaries[1].from_ == mock_mails[1].from_
    assert summaries[1].count == 2
    assert summaries[1].first_datetime == mock_mails[0].date
    assert summaries[1].last_datetime == mock_mails[1].date
    assert summaries[1].age == 0
    assert summaries[1].action == Action.NONE