from mailtidy.mailtidy import IMAPConnectionData    
from yaml import unsafe_load as load_yaml

def test_constructor():
    data = IMAPConnectionData(imap_server='imap.someplace.com', port=993, email='user@someplace.com', password='pass')
    assert data.imap_server == 'imap.someplace.com'
    assert data.port == 993
    assert data.email == 'user@someplace.com'
    assert data.password == 'pass'

def test_load_yaml():
    yaml_str = """
    imap_server: imap.someplace.com
    port: 993
    email: user@someplace.com
    password: pass
    """
    data = IMAPConnectionData(**load_yaml(yaml_str))
    assert data.imap_server == 'imap.someplace.com'
    assert data.port == 993
    assert data.email == 'user@someplace.com'
    assert data.password == 'pass'      