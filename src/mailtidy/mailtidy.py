#!/usr/bin/env python3
import argparse
import logging
logger = logging.getLogger(__name__)
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from imap_tools import MailBox, A, MailMessage
from tqdm import tqdm
from yaml import dump, unsafe_load as load_yaml, YAMLObject, add_constructor, add_representer
from pathlib import Path
from typing import Optional, List, Iterable, Sequence, TypeVar, Union, Tuple, Iterator

DEFAULT_BULK_SIZE = 250
DEFAULT_CONNECTION_DATA_PATH = Path.home() / ".mail_client" / "connection_data.yml"

class Action(Enum):
    """Represents the possible actions to take on an email."""
    DELETE = "delete"
    ARCHIVE = "archive"
    PRINT_ALL = "print_all"
    PRINT_HEADERS = "print_headers"
    FLAG_SEEN = "seen"
    FLAG_ANSWERED = "answered"
    FLAG_FLAGGED = "flagged"
    FLAG_DELETED = "deleted"
    FLAG_DRAFT = "draft"
    FLAG_RECENT = "recent"
    NONE = "none"

action_representer = lambda dumper, data: dumper.represent_scalar(u'!Action', data.value)
add_representer(Action, action_representer)
add_constructor('!Action', lambda loader, node: Action(loader.construct_scalar(node)))

@dataclass
class SenderSummary(YAMLObject):
    """Represents a summary of emails received from a sender."""
    from_: str
    count: int = 0
    first_datetime: datetime = None
    last_datetime: datetime = None
    age: int = 0
    action: Action = Action.NONE
    yaml_tag = u'!SenderSummary'

@dataclass
class IMAPConnectionData:
    """Represents a connection to the mailbox."""
    imap_server: str
    email: str
    password: str
    port: int 

class MailboxManager:
    """Handles mailbox operations."""
    
    def __init__(self, connection_data: IMAPConnectionData, dry_run: bool = False, unique=False, mailbox: MailBox = None) -> None:
        """Initialize the mailbox manager.
        """
        self.imap_server = connection_data.imap_server
        self.port = connection_data.port
        self.email = connection_data.email
        self.password = connection_data.password
        self.dry_run = dry_run
        self.unique = unique
        if mailbox:
            self.mailbox = mailbox
        else:
            self.mailbox = MailBox(self.imap_server, self.port)
        self.logged_in = False

    def connect(self) -> None:
        """Connect to the mailbox."""
        self.mailbox.login(self.email, self.password)
        self.logged_in = True
        logger.info(f"Connected to mailbox for {self.email} at {self.imap_server}:{self.port} containing {len(self.mailbox.uids())} messages.")
    
    def disconnect(self) -> None:
        """Disconnect from the mailbox."""
        if self.mailbox:
            self.mailbox.logout()
            self.logged_in = False
            logger.info(f"Disconnected from mailbox for {self.email} at {self.imap_server}:{self.port}.")
    
    def fetch_uids(self, uids: Sequence[str], mark_seen: bool = False, headers_only: bool = False, bulk=DEFAULT_BULK_SIZE) -> Iterable:
        """Fetch emails by their UIDs.
        
        Args:
            uids: Sequence of email UIDs to fetch
        
        Returns:
            Iterable of email messages corresponding to the provided UIDs
        """
        if not self.logged_in:
            self.connect()
        message_parts = \
            f"(BODY{'' if mark_seen else '.PEEK'}[{'HEADER' if headers_only else ''}] UID FLAGS RFC822.SIZE)"
        return self.mailbox._fetch_in_bulk(uid_list=uids, message_parts=message_parts, reverse=False, bulk=3)
    
    def fetch_summaries(self) -> dict:
        '''Fetch a map of summaries of emails keyed by sender.
        '''
        if not self.logged_in:
            self.connect()
        summaries = {}

        with tqdm(total=len(self.mailbox.uids()), desc="Processing emails") as pbar:
            for msg in self.mailbox.fetch(mark_seen=False, headers_only=False, bulk=DEFAULT_BULK_SIZE):
                self.summarise_message(summaries, msg)
                pbar.update(1)
        logger.info(f"Found {len(summaries)} senders.")
        return summaries
    
    def summarise_message(self, summaries: dict, msg: MailMessage) -> None:
        if not msg.from_:
            logger.warning(f"Email with UID {msg.uid} has no sender. Skipping.")
            return
        if not msg.date:
            logger.warning(f"Email with UID {msg.uid} has no date. Skipping.")
            return
        if self.unique:
            # If unique is True, use the entire sender string as the key, which may include the name and email address.
            sender = msg.from_
        else:
            # Else extract the domain from the sender's email address. If there is no domain, use the entire sender string as the key.
            sender = msg.from_.split("@")[-1] if "@" in msg.from_ else msg.from_
        if sender in summaries:
            summary = summaries[sender]
            summary.count += 1
            # There is a mix of timezone-aware and timezone-naive datetimes in the mailbox.
            # Convert them to a timestamps before comparing them.  
            if msg.date.timestamp() < summary.first_datetime.timestamp():
                summary.first_datetime = msg.date
            if msg.date.timestamp() > summary.last_datetime.timestamp():
                summary.last_datetime = msg.date
        else:
            summaries[sender] = SenderSummary(sender, 1, msg.date, msg.date)
        logger.debug(summaries[sender])
    
    '''Generate search criteria for fetching emails from a specific sender that are older than a certain age in
    days.
    NOTE: The imap_tools library does not support searching by age directly, so we need to calculate the target date and use it in the search criteria.
    NOTE: The imap_tools library returns all emails when the sender is an empty string, so we need to handle that case separately to avoid fetching the entire mailbox when the sender is not specified.
    '''
    def getCrieria(self, from_: str, age: int) -> A:
        assert age >= 0, "Age must be a non-negative integer"
        assert from_, "From address must be a non-empty string"
        target_date = date.today() - timedelta(days=age)
        return A(from_ = from_, sent_date_lt=target_date)


    '''Fetch the UIDs of emails from a specific sender that are older than a certain age in days.
    '''
    def getUids(self, from_: str, age: int) -> Sequence[str]:
        if not self.logged_in:
            self.connect()
        return self.mailbox.uids(self.getCrieria(from_, age))
    
    def delete_uids(self, uids: Sequence[str], bulk = DEFAULT_BULK_SIZE) -> Iterable:
        if not self.logged_in:
            self.connect()
        deleted = []
        if self.dry_run:
            logger.info(f"DRY RUN: Would delete {len(uids)} emails in batches of {bulk} ...")
        else:
            logger.info(f"Deleting {len(uids)} emails in batches of {bulk} ...")
            deleted =self.mailbox.delete(uids, bulk)
        return deleted
    
    '''Move emails with the specified UIDs to the "Archive" folder.
    '''
    def archive_uids(self, uids: Sequence[str], bulk = DEFAULT_BULK_SIZE) -> Iterable:
        if not self.logged_in:
            self.connect()
        archived = []
        if self.dry_run:
                logger.info(f"DRY RUN: Would archive {len(uids)} emails in batches of {bulk} ...")
        else:
            logger.info(f"Archiving {len(uids)} emails in batches of {bulk} ...")
            archived = self.mailbox.move(uids, "Archive", chunks=bulk)
        return archived

    def print_all_uids(self, uids: Sequence[str], bulk = DEFAULT_BULK_SIZE) -> None:
        if not self.logged_in:
            self.connect()
        for message in self.fetch_uids(uids, mark_seen=False, headers_only=False, bulk=bulk):
            print(message)

    def print_headers_uids(self, uids: Sequence[str], bulk = DEFAULT_BULK_SIZE) -> None:
        if not self.logged_in:
            self.connect()
        for message in self.fetch_uids(uids, mark_seen=False, headers_only=True, bulk=bulk):
            print(message)

class AbstractCommand(ABC):
    """Abstract base class for commands to execute on the mailbox."""
    @abstractmethod
    def execute(self) -> int:
        """Execute the command and return an exit code."""
        pass

class SummaryCommand:
    """Command to summarise emails in the mailbox."""
    def __init__(self, manager: MailboxManager, output_file: str, unique: bool = False) -> None:
        self.manager = manager
        self.output_file = output_file
        self.unique = unique

    def execute(self) -> int:
        """Execute the summarisation command."""
        summaries = self.manager.fetch_summaries()
        with open(self.output_file, mode="wt", encoding="utf-8") as file:
            logger.info(f"Dumping summaries to {self.output_file} ...")
            file.write(dump(sorted(summaries.values(), key=lambda s: s.from_)))
        return 0

class ApplyCommand:
    """Command to apply actions to emails in the mailbox based on summaries."""
    def __init__(self, manager: MailboxManager, input_file: str, dry_run: bool = False) -> None:
        self.manager = manager
        self.input_file = input_file
        self.dry_run = dry_run

    def execute(self) -> int:
        """Execute the apply command."""
        with open(self.input_file, mode="rt", encoding="utf-8") as file:
            summaries = load_yaml(file)
        logger.info(f"Applying {len(summaries)} actions from {self.input_file} ...")
        for summary in summaries:
            logger.info(f"Processing sender \"{summary.from_}\" with action {summary.action} ...")
            try:
                uids = self.manager.getUids(summary.from_, summary.age)
                if summary.action == Action.NONE:
                    pass
                if summary.action == Action.DELETE:
                    self.manager.delete_uids(uids)
                elif summary.action == Action.ARCHIVE:
                    self.manager.archive_uids(uids)
                elif summary.action == Action.PRINT_ALL:
                    self.manager.print_all_uids(uids)
                elif summary.action == Action.PRINT_HEADERS:
                    self.manager.print_headers_uids(uids)
                #TODO: Add support for flagging actions.
                elif summary.action in [Action.FLAG_ANSWERED, Action.FLAG_DELETED, Action.FLAG_DRAFT, Action.FLAG_FLAGGED, Action.FLAG_RECENT, Action.FLAG_SEEN]:
                    logger.warning(f"Flagging action {summary.action} is not yet implemented. Skipping sender {summary.from_}.")
            except Exception as e:
                logger.error(f"Error processing sender {summary.from_}: {e}")   
            
        return 0

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='Mail client for fetching email summaries')
    parser.add_argument('command', choices=['summarise', 'apply'], help='Command to execute: summarise or apply')
    parser.add_argument('-f', '--file', type=str, default='summaries.yml',
                       help='File to save email summaries (default: summaries.yml)')
    parser.add_argument('-d', '--debug', action='store_true',
                       help='Enable debug logging  (default: False)')
    parser.add_argument('-n', '--dry-run', action='store_true',
                       help='Perform a dry run without making changes  (default: False')
    parser.add_argument('-u', '--unique', action='store_false',
                       help='Summarise by unique sender (default: False)')
    #TODO: Maybe add support for specifying connection data via command-line arguments, with the option to load from a YAML file as a fallback.
    #parser.add_argument('-i', '--imap-server', type=str,
    #                   help='IMAP server address)
    #parser.add_argument('-p', '--port', type=int,
    #                   help='IMAP server port')
    #parser.add_argument('--email', type=str,
    #                   help='Email address for authentication')
    #parser.add_argument('--password', type=str,
    #                   help='Password for authentication')
    
    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        with open(DEFAULT_CONNECTION_DATA_PATH, mode="rt", encoding="utf-8") as file:
            logger.info(f"Loading connection data from {DEFAULT_CONNECTION_DATA_PATH}")
            imap_data = IMAPConnectionData(**load_yaml(file))
    except FileNotFoundError:
        logger.error(f"Connection data file not found: {DEFAULT_CONNECTION_DATA_PATH}")
        exit(1)
    logger.debug(f"Loaded connection data for: {imap_data.email} at {imap_data.imap_server}:{imap_data.port}")
    manager = MailboxManager(imap_data, dry_run=args.dry_run, unique=args.unique)
    try:
        with manager.connect() as mailbox:
            if args.command == 'summarise':
                rc = SummaryCommand(manager, args.file).execute()
            elif args.command == 'apply':
                rc = ApplyCommand(manager, args.file).execute()
    finally:
        if manager.mailbox:
            #manager.disconnect()
            pass 
    exit(rc)

if __name__ == "__main__":
    raise SystemExit(main())