from mailbox import mbox

from mailtidy.mailtidy import MailboxManager 
from pytest_mock import MockerFixture 

def test_constructor(imap_connection_data, mock_mailbox):
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    assert manager.imap_server == imap_connection_data.imap_server
    assert manager.port == imap_connection_data.port
    assert manager.email == imap_connection_data.email
    assert manager.password == imap_connection_data.password       
    assert manager.mailbox == mock_mailbox 

def test_constructor_defaults(imap_connection_data, mock_mailbox):
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    assert manager.imap_server == imap_connection_data.imap_server
    assert manager.port == imap_connection_data.port
    assert manager.email == imap_connection_data.email
    assert manager.password == imap_connection_data.password
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

def test_print_all_uids(imap_connection_data, mock_mailbox, mock_uids, mock_mails, capsys):
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    uids = manager.getUids(from_ = mock_mails[0].from_, age=0)
    manager.print_all_uids(uids)
    captured = capsys.readouterr()
    assert mock_mails[0].from_ in captured.out
    assert mock_mails[0].subject in captured.out    
    assert mock_mails[0].date.strftime('%a, %d %b %Y %H:%M:%S %z') in captured.out 
    txt = mock_mails[0].text.replace('\n', '').replace('\r', '')
    captured_txt = captured.out.replace('\n', '').replace('\r', '')
    assert txt in captured_txt

def test_print_header_uids(imap_connection_data, mock_mailbox, mock_uids, mock_mails, capsys):
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    uids = manager.getUids(from_ = mock_mails[0].from_, age=0)
    manager.print_headers_uids(uids)
    captured = capsys.readouterr()
    assert mock_mails[0].from_ in captured.out
    assert mock_mails[0].subject in captured.out    
    #assert mock_mails[0].date.strftime('%Y-%m-%d %H:%M:%S') in captured.out
    assert mock_mails[0].date.strftime('%a, %d %b %Y %H:%M:%S %z') in captured.out   

def test_mbox_uids(imap_connection_data, mock_mailbox, mock_uids, mock_mails, tmp_path):
    tmp_mailbox_path = tmp_path / "test.mbox"
    manager = MailboxManager(connection_data=imap_connection_data, mailbox=mock_mailbox)
    uids = manager.getUids(from_ = mock_mails[0].from_, age=0)
    manager.mbox_uids(tmp_mailbox_path, uids[:1])
    mb = mbox(tmp_mailbox_path, create=False)  # This will raise an error if the mbox file was not created successfully
    mbmessage =  mb.values()[0]
    assert mbmessage['From'] == mock_mails[0].from_values.full
    assert mbmessage['Subject'] == mock_mails[0].subject
    assert mbmessage.get_payload().rstrip('\n') == mock_mails[0].text.rstrip('\r\n')
    mb.close()