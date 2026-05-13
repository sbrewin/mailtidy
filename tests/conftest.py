from pyexpat.errors import messages

import pytest

from mailtidy.mailtidy import DEFAULT_BULK_SIZE, IMAPConnectionData, SenderSummary, Action
import datetime
from dataclasses import dataclass
from datetime import timezone, timedelta
from imap_tools import MailMessage, message

pytest_plugins = ("pytest_mock",)

@pytest.fixture
def mock_mailbox(mocker, mock_uids, mock_mails, mock_db):
    '''A fixture that provides a mock MailBox instance for testing.'''
    mock_mailbox = mocker.Mock(name='MockMailbox', autospec=True)
    # Disable the login method, which requires a real connection to an IMAP server, and set up the uids method to return a fixed list of UIDs for testing.
    mock_mailbox.patch('login', lambda : None) 
    # Simulate the uids method to return a fixed list of UIDs
    mock_mailbox.uids.return_value = mock_uids
    # Simulate the fetch method to return a fixed list of MailMessage instances based on the provided UIDs
    mock_mailbox.fetch.return_value = mock_mails
    # Disable the _get_mailbox_client method, which requires a real IMAP server connection
    mock_mailbox.patch('_get_mailbox_client', lambda: None)
    # Simulate the delete method to remove UIDs from the mock_uids list when called
    def delete_side_effect(*args, **kwargs):
        print(f'mock_mailbox.delete called with args: {args}, kwargs: {kwargs}')
        mock_uids[:] = [uid for uid in mock_uids if uid not in args[0]]  # Remove the deleted UIDs from the mock_uids list
        return None
    mock_mailbox.delete.side_effect = delete_side_effect
    # Simulate the _fetch_in_bulk method to return a fixed list of MailMessage instances based on the provided UIDs
    def _fetch_in_bulk_side_effect(uid_list, message_parts, reverse=False, bulk=DEFAULT_BULK_SIZE):
        print(f'mock_mailbox._fetch_in_bulk called with uid_list: {uid_list}, message_parts: {message_parts}, reverse: {reverse}, bulk: {bulk}')
        messages = []
        for uid in uid_list:
            if uid not in mock_uids:
                print(f'UID {uid} not found in mock_uids: {mock_uids}')
            else:
                message = mock_db[uid]
                #bytes2 = ((b'3861 (UID 74982 FLAGS (\\Seen) RFC822.SIZE 3388 BODY[] {3388}', raw_message_data), b')')
                bytes = ((b'', message.obj.as_bytes()), b')')
                messages.append(bytes)
        print(f'mock_mailbox._fetch_in_bulk returning: {messages}')
        return messages
    mock_mailbox._fetch_in_bulk.side_effect = _fetch_in_bulk_side_effect

    return mock_mailbox

@pytest.fixture
def imap_connection_data():
    return IMAPConnectionData(imap_server='imap.someplace.com', port=993, email='someone@someplace.com', password='pass')

@pytest.fixture
def sample_mail_func() -> callable:
    '''A fixture that provides a function to generate simple MailMessage instances for testing.
    Nothing fancy is required, just enough to test the functionality of the MailboxManager and supporting classes.'''
    def _sample_mail(sender: str, date: str) -> MailMessage:
        txt = "Delivered-To: mailtest@somewhere.com\r\n"
        txt +=  "Return-Path: <" + sender + ">\r\n"
        txt += "Received: from node.example by x.y.test; " + date + "\r\n"
        txt +=  "Message-Id: <1234@mtest.machine.local>\r\n"
        txt +=  "From: Test User <" + sender + ">\r\n"
        txt +=  "To: Mail Test <mailtest@somewhere.com>\r\n"
        txt +=  "Content-Type: text/plain; charset=US-ASCII; format=flowed\r\n"
        txt +=  "Content-Transfer-Encoding: 7bit\r\n"
        txt +=  "Mime-Version: 1.0\r\n"
        txt +=  "Subject: Sample Email\r\n"
        txt +=  "Date: " + date + "\r\n"
        txt +=  "\r\n"
        txt +=  "This is a sample email for testing purposes.\r\n"
        bytes_txt = txt.encode(encoding='utf-8')
        return MailMessage.from_bytes(bytes_txt)
        #return MailMessage.from_bytes(txt.encode(encoding='utf-8'))
    return _sample_mail

@pytest.fixture
def mock_db(mocker, sample_mail_func) -> dict: 
    '''A fixture that provides a mock database for testing.'''
    db = {}
    db[1] = sample_mail_func(sender="someone@somewhere.com", date="Tue, 14 Apr 2026 20:05:05 -0800")
    db[2] = sample_mail_func(sender="someone@somewhere.com", date="Wed, 15 Apr 2026 20:05:05 -0800")
    db[3] = sample_mail_func(sender="someone@elsewhere.com", date="Wed, 15 Apr 2026 20:05:05 -0800")
    return db

@pytest.fixture
def mock_uids(mocker, mock_db) -> list:      
    '''A fixture that provides a mock list of UIDs for testing.'''
    return list(mock_db.keys())

@pytest.fixture
def mock_mails(mocker, mock_db) -> list:      
    '''A fixture that provides a mock list of MailMessage instances for testing.'''
    return list(mock_db.values())