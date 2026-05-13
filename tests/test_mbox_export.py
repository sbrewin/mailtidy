from mailbox import mbox, mboxMessage

def test_mbox_message(mock_mails):
    mail = mock_mails[0]
    mbmessage =  mboxMessage(mail.obj)
    assert mbmessage['From'] == mock_mails[0].from_values.full
    assert mbmessage['Subject'] == mock_mails[0].subject
    assert mbmessage.get_payload() == mock_mails[0].text