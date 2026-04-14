from mailtidy.mailtidy import MailboxManager 
from pytest_mock import MockerFixture 

def test_constructor(imap_connection_data, mock_mailbox):
    manager = MailboxManager(connection_data=imap_connection_data, dry_run=True, unique=True, mailbox=mock_mailbox)
    assert manager.imap_server == imap_connection_data.imap_server
    assert manager.port == imap_connection_data.port
    assert manager.email == imap_connection_data.email
    assert manager.password == imap_connection_data.password
    assert manager.dry_run is True
    assert manager.unique is True              
    assert manager.mailbox == mock_mailbox 

def test_constructor_defaults(imap_connection_data, mock_mailbox):
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    assert manager.imap_server == imap_connection_data.imap_server
    assert manager.port == imap_connection_data.port
    assert manager.email == imap_connection_data.email
    assert manager.password == imap_connection_data.password
    assert manager.dry_run is False
    assert manager.unique is False
    assert manager.mailbox == mock_mailbox

def test_connect(imap_connection_data, mock_mailbox):
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    manager.connect()
    assert manager.logged_in
    manager.disconnect()
    assert not manager.logged_in

def test_get_uids(imap_connection_data, mock_mailbox, mock_mails, mock_uids):
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    uids = manager.getUids(from_ = mock_mails[0].from_, age=0)
    assert uids == mock_uids

def test_fetch_summaries(imap_connection_data, mock_mailbox, mock_mails):
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    count = 0
    for summary in manager.fetch_summaries().values():
        count += summary.count
    assert count == len(mock_mails)
    assert list(manager.fetch_summaries().keys())[0] == mock_mails[0].from_.split("@")[-1]
    assert list(manager.fetch_summaries().keys())[1] == mock_mails[2].from_.split("@")[-1]
    assert list(manager.fetch_summaries().values())[0].first_datetime == mock_mails[0].date
    assert list(manager.fetch_summaries().values())[0].last_datetime == mock_mails[1].date
    assert list(manager.fetch_summaries().values())[1].first_datetime == mock_mails[2].date
    assert list(manager.fetch_summaries().values())[1].last_datetime == mock_mails[2].date

def test_delete_uids(imap_connection_data, mock_mailbox, mock_uids, mock_mails):
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    uids = manager.getUids(from_ = mock_mails[0].from_, age=0)
    len_uids = len(uids)
    manager.delete_uids(uids[:1])
    assert len(uids) == len_uids - 1