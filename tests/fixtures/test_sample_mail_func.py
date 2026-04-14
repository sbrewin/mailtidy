from datetime import datetime,timezone

def test_sample_mail_func(sample_mail_func):
    now = datetime.now(timezone.utc)
    date_str = now.strftime('%a, %d %b %Y %H:%M:%S %z')
    sample_mail = sample_mail_func(sender="someone@someplace.com", date=date_str)
    assert sample_mail.from_ == 'someone@someplace.com'
    assert sample_mail.date == now.replace(microsecond=0)  # Ignore microseconds for comparison
    assert sample_mail.subject == 'Sample Email'
    assert sample_mail.text == 'This is a sample email for testing purposes.'
    assert sample_mail.attachments == []
