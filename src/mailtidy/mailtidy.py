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
    
    def __init__(self, connection_data: IMAPConnectionData, dry_run: bool = False, unique=False):
        """Initialize the mailbox manager.
        """
        self.imap_server = connection_data.imap_server
        self.port = connection_data.port
        self.email = connection_data.email
        self.password = connection_data.password
        self.dry_run = dry_run
        self.unique = unique
        self.mailbox = None
    
    def connect(self) -> MailBox:
        """Connect to the mailbox."""
        self.mailbox = MailBox(self.imap_server, self.port).login(self.email, self.password)
        logger.info(f"Connected to mailbox for {self.email} at {self.imap_server}:{self.port} containing {len(self.mailbox.uids())} messages.")
        return self.mailbox
    
    def disconnect(self) -> None:
        """Disconnect from the mailbox."""
        if self.mailbox:
            self.mailbox.logout()
    
    def fetch_all_emails(self, mark_seen: bool = False, headers_only: bool = False, bulk=DEFAULT_BULK_SIZE) -> Iterable:
        """Fetch all emails from the inbox.
        
        Yields:
            Email messages from the mailbox
        """
        if not self.mailbox:
            self.connect()
        
        # FIXME: If headers_only is True, the msg.date field is not populated, which breaks the summary logic. Need to find a way to fetch headers without losing date information.
        # FIXME: Are the datetimes imoportant? If not, we can just fetch headers and ignore the date field.
        return self.mailbox.fetch(mark_seen, headers_only, bulk)
    
    def fetch_uids(self, uids: Sequence[str], mark_seen: bool = False, headers_only: bool = False, bulk=DEFAULT_BULK_SIZE) -> Iterable:
        """Fetch emails by their UIDs.
        
        Args:
            uids: Sequence of email UIDs to fetch
        
        Returns:
            Iterable of email messages corresponding to the provided UIDs
        """
        if not self.mailbox:
            self.connect()
        message_parts = \
            f"(BODY{'' if mark_seen else '.PEEK'}[{'HEADER' if headers_only else ''}] UID FLAGS RFC822.SIZE)"
        return self.mailbox._fetch_in_bulk(uid_list=uids, message_parts=message_parts, reverse=False, bulk=3)
    
    def fetch_summaries_old(self) -> dict:
        '''Fetch a map of summaries of emails keyed by sender.
        '''
        if not self.mailbox:
            self.connect()
        summaries = {}

        with tqdm(total=len(self.mailbox.uids()), desc="Processing emails") as pbar:
            for msg in self.mailbox.fetch(mark_seen=False, headers_only=False, bulk=DEFAULT_BULK_SIZE):
                if msg.from_ in summaries:
                    summary = summaries[msg.from_]
                    summary.count += 1
                    # There is a mix of timezone-aware and timezone-naive datetimes in the mailbox.
                    # Convert them to a timestamps before comparing them.  
                    if msg.date.timestamp() < summary.first_datetime.timestamp():
                        summary.first_datetime = msg.date
                    if msg.date.timestamp() > summary.last_datetime.timestamp():
                        summary.last_datetime = msg.date
                else:
                    summaries[msg.from_] = SenderSummary(msg.from_, 1, msg.date, msg.date) 
                pbar.update(1)
                logger.debug(summaries[msg.from_])
        logger.info(f"Found {len(summaries)} unique senders.")
        return summaries
    
    # FIXME  Experiment with fetching summaries by domain 
    def fetch_domain_summaries(self) -> dict:
        '''Fetch a map of summaries of emails keyed by the domain of the sender.
        '''
        if not self.mailbox:
            self.connect()
        summaries = {}

        with tqdm(total=len(self.mailbox.uids()), desc="Processing emails") as pbar:
            for msg in self.mailbox.fetch(mark_seen=False, headers_only=False, bulk=DEFAULT_BULK_SIZE):
                from_domain = msg.from_.split("@")[-1] if "@" in msg.from_ else ""
                if from_domain in summaries:
                    summary = summaries[from_domain]
                    summary.count += 1
                    # There is a mix of timezone-aware and timezone-naive datetimes in the mailbox.
                    # Convert them to a timestamps before comparing them.  
                    if msg.date.timestamp() < summary.first_datetime.timestamp():
                        summary.first_datetime = msg.date
                    if msg.date.timestamp() > summary.last_datetime.timestamp():
                        summary.last_datetime = msg.date
                else:
                    summaries[from_domain] = SenderSummary(from_domain, 1, msg.date, msg.date) 
                pbar.update(1)
                logger.debug(summaries[from_domain])
        logger.info(f"Found {len(summaries)} unique sender domains.")
        return summaries
    
    def fetch_summaries(self) -> dict:
        '''Fetch a map of summaries of emails keyed by sender.
        '''
        if not self.mailbox:
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
            sender = msg.from_
        else:
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

    # TODO: Remove this and add to unit tests instead. This is just a temporary method for testing the apply logic without needing to connect to an actual mailbox and fetch summaries.
    def fetch_summaries_mock(self):  
        list = [
            SenderSummary(from_='', count=68, first_datetime=datetime(1900, 1, 1, 0, 0), last_datetime=datetime(2024, 8, 24, 5, 17, 3, tzinfo=timezone(timedelta(seconds=7200)))),
            SenderSummary(from_='""@gmail.com', count=1, first_datetime=datetime(2023, 3, 18, 19, 3, 3, tzinfo=timezone(timedelta(seconds=3600))), last_datetime=datetime(2023, 3, 18, 19, 3, 3, tzinfo=timezone(timedelta(seconds=3600)))),
            SenderSummary(from_="'like@cafe24.com", count=2, first_datetime=datetime(2024, 4, 11, 2, 47, 34, tzinfo=timezone(timedelta(days=-1, seconds=61200))), last_datetime=datetime(2026, 2, 14, 11, 13, 35)),
            SenderSummary(from_='00001795@ipresspublicas.gob.pe', count=1, first_datetime=datetime(2023, 6, 8, 16, 55, 21, tzinfo=timezone(timedelta(days=-1, seconds=61200))), last_datetime=datetime(2023, 6, 8, 16, 55, 21, tzinfo=timezone(timedelta(days=-1, seconds=61200)))),
            SenderSummary(from_='00@0.0.0.0.batamproject.com', count=1, first_datetime=datetime(2023, 9, 11, 23, 6, 47, tzinfo=timezone(timedelta(days=-1, seconds=75600))), last_datetime=datetime(2023, 9, 11, 23, 6, 47, tzinfo=timezone(timedelta(days=-1, seconds=75600)))),
            SenderSummary(from_='0maha@capitolmedicalclinic.com', count=1, first_datetime=datetime(2026, 2, 8, 16, 2, 27, tzinfo=timezone(timedelta(days=-1, seconds=68400))), last_datetime=datetime(2026, 2, 8, 16, 2, 27, tzinfo=timezone(timedelta(days=-1, seconds=68400)))),
            SenderSummary(from_='10-secondritual@livinghelha.ru.com', count=1, first_datetime=datetime(2022, 9, 3, 2, 16, 6, tzinfo=timezone(timedelta(days=-1, seconds=61200))), last_datetime=datetime(2022, 9, 3, 2, 16, 6, tzinfo=timezone(timedelta(days=-1, seconds=61200)))),
            SenderSummary(from_='123456@xxdlife.com', count=2, first_datetime=datetime(2022, 9, 16, 9, 49, 17, tzinfo=timezone(timedelta(seconds=3600))), last_datetime=datetime(2022, 10, 1, 16, 46, 38, tzinfo=timezone(timedelta(days=-1, seconds=61200)))),
            SenderSummary(from_='1312178@utp.edu.pe', count=1, first_datetime=datetime(2024, 12, 27, 10, 39, 2, tzinfo=timezone.utc), last_datetime=datetime(2024, 12, 27, 10, 39, 2, tzinfo=timezone.utc)),
            SenderSummary(from_='1330037@utp.edu.pe', count=1, first_datetime=datetime(2024, 11, 27, 9, 43, 20, tzinfo=timezone.utc), last_datetime=datetime(2024, 11, 27, 9, 43, 20, tzinfo=timezone.utc)),
            SenderSummary(from_='14155-olca20@olcaescolas.onmicrosoft.com', count=1, first_datetime=datetime(2024, 12, 31, 10, 15, 31, tzinfo=timezone.utc), last_datetime=datetime(2024, 12, 31, 10, 15, 31, tzinfo=timezone.utc)),
            SenderSummary(from_='1547507@senati.pe', count=1, first_datetime=datetime(2025, 1, 10, 15, 22, 11, tzinfo=timezone.utc), last_datetime=datetime(2025, 1, 10, 15, 22, 11, tzinfo=timezone.utc)),
            SenderSummary(from_='1634265@utp.edu.pe', count=1, first_datetime=datetime(2024, 10, 9, 5, 45, 12, tzinfo=timezone.utc), last_datetime=datetime(2024, 10, 9, 5, 45, 12, tzinfo=timezone.utc)),
            SenderSummary(from_='1837036@std.hu.edu.jo', count=1, first_datetime=datetime(2024, 11, 15, 14, 2, 13, tzinfo=timezone.utc), last_datetime=datetime(2024, 11, 15, 14, 2, 13, tzinfo=timezone.utc)),
            SenderSummary(from_='1951015065@kientruchanoi.edu.vn', count=1, first_datetime=datetime(2024, 9, 22, 14, 57, 55, tzinfo=timezone.utc), last_datetime=datetime(2024, 9, 22, 14, 57, 55, tzinfo=timezone.utc)),
            SenderSummary(from_='1996.kanchanmeena@bose.res.in', count=1, first_datetime=datetime(2025, 2, 23, 18, 5, 13, tzinfo=timezone(timedelta(seconds=19800))), last_datetime=datetime(2025, 2, 23, 18, 5, 13, tzinfo=timezone(timedelta(seconds=19800)))),
            SenderSummary(from_='1C1RXQR_en__1122__1122@grupouniversal.local', count=1, first_datetime=datetime(2024, 8, 10, 15, 50, 37, tzinfo=timezone.utc), last_datetime=datetime(2024, 8, 10, 15, 50, 37, tzinfo=timezone.utc)),
            SenderSummary(from_='20060601.sang@student.iuh.edu.vn', count=1, first_datetime=datetime(2024, 9, 6, 18, 28, 12, tzinfo=timezone.utc), last_datetime=datetime(2024, 9, 6, 18, 28, 12, tzinfo=timezone.utc)),
            SenderSummary(from_='2007221706@alu.uap.edu.pe', count=1, first_datetime=datetime(2024, 8, 23, 17, 7, 3, tzinfo=timezone.utc), last_datetime=datetime(2024, 8, 23, 17, 7, 3, tzinfo=timezone.utc)),
            SenderSummary(from_='200802181@students.uajy.ac.id', count=1, first_datetime=datetime(2024, 9, 9, 20, 23, 46, tzinfo=timezone.utc), last_datetime=datetime(2024, 9, 9, 20, 23, 46, tzinfo=timezone.utc)),
            SenderSummary(from_='2011106900515@alunocarioca.rio', count=1, first_datetime=datetime(2024, 11, 22, 13, 28, 30, tzinfo=timezone.utc), last_datetime=datetime(2024, 11, 22, 13, 28, 30, tzinfo=timezone.utc)),
            SenderSummary(from_='2013305257@alu.uap.edu.pe', count=1, first_datetime=datetime(2024, 9, 12, 8, 26, 48, tzinfo=timezone.utc), last_datetime=datetime(2024, 9, 12, 8, 26, 48, tzinfo=timezone.utc)),
            SenderSummary(from_='2014033280011@alunocarioca.rio', count=1, first_datetime=datetime(2024, 12, 19, 16, 34, 36, tzinfo=timezone.utc), last_datetime=datetime(2024, 12, 19, 16, 34, 36, tzinfo=timezone.utc)),
            SenderSummary(from_='20167308@stu.uob.edu.bh', count=1, first_datetime=datetime(2024, 12, 29, 12, 17, 29, tzinfo=timezone.utc), last_datetime=datetime(2024, 12, 29, 12, 17, 29, tzinfo=timezone.utc)),
            SenderSummary(from_='20213362024@ogr.akdeniz.edu.tr', count=1, first_datetime=datetime(2024, 9, 16, 20, 12, 3, tzinfo=timezone.utc), last_datetime=datetime(2024, 9, 16, 20, 12, 3, tzinfo=timezone.utc)),
            SenderSummary(from_='20SecondPainFix@sonoblisspro.services', count=1, first_datetime=datetime(2023, 4, 21, 21, 39, 1, tzinfo=timezone(timedelta(days=-1, seconds=61200))), last_datetime=datetime(2023, 4, 21, 21, 39, 1, tzinfo=timezone(timedelta(days=-1, seconds=61200)))),
            SenderSummary(from_='26354@galahitiyawacc.com', count=1, first_datetime=datetime(2024, 12, 22, 12, 58, 58, tzinfo=timezone.utc), last_datetime=datetime(2024, 12, 22, 12, 58, 58, tzinfo=timezone.utc)),
            SenderSummary(from_='3ssolar@teb.msgfocus.com', count=1, first_datetime=datetime(2024, 10, 3, 11, 26, 23, tzinfo=timezone(timedelta(seconds=3600))), last_datetime=datetime(2024, 10, 3, 11, 26, 23, tzinfo=timezone(timedelta(seconds=3600)))),
            SenderSummary(from_='3tx40pvnjfg0bfl@marketplace.amazon.co.uk', count=1, first_datetime=datetime(2022, 9, 14, 9, 34, 43, tzinfo=timezone.utc), last_datetime=datetime(2022, 9, 14, 9, 34, 43, tzinfo=timezone.utc)),
            SenderSummary(from_='3w874r0fz9l1jg5@marketplace.amazon.co.uk', count=1, first_datetime=datetime(2023, 6, 7, 8, 10, 18, tzinfo=timezone.utc), last_datetime=datetime(2023, 6, 7, 8, 10, 18, tzinfo=timezone.utc)),
            SenderSummary(from_='42bqTyywY9uTizqjTsc4-tsyEFVJ6@servmngrs5.solconfi.com.co', count=1, first_datetime=datetime(2024, 6, 8, 2, 38, 11, tzinfo=timezone(timedelta(seconds=25200))), last_datetime=datetime(2024, 6, 8, 2, 38, 11, tzinfo=timezone(timedelta(seconds=25200)))),
            SenderSummary(from_='4407761260966i@gmail.com', count=2, first_datetime=datetime(2022, 11, 24, 15, 12, 11, tzinfo=timezone(timedelta(days=-1, seconds=64800))), last_datetime=datetime(2022, 11, 24, 23, 48, 36, tzinfo=timezone(timedelta(days=-1, seconds=64800))))
            ]     
        summaries = {}
        for summary in list:
            summaries[summary.from_] = summary
        return summaries
    
    def fetch_domain_summaries_mock(self):  
        list = [
            SenderSummary(from_='', count=68, first_datetime=datetime(1900, 1, 1, 0, 0), last_datetime=datetime(2024, 8, 24, 5, 17, 3, tzinfo=timezone(timedelta(seconds=7200)))),
            SenderSummary(from_='gmail.com', count=1, first_datetime=datetime(2023, 3, 18, 19, 3, 3, tzinfo=timezone(timedelta(seconds=3600))), last_datetime=datetime(2023, 3, 18, 19, 3, 3, tzinfo=timezone(timedelta(seconds=3600)))),
            SenderSummary(from_="'cafe24.com", count=2, first_datetime=datetime(2024, 4, 11, 2, 47, 34, tzinfo=timezone(timedelta(days=-1, seconds=61200))), last_datetime=datetime(2026, 2, 14, 11, 13, 35)),
            SenderSummary(from_='ipresspublicas.gob.pe', count=1, first_datetime=datetime(2023, 6, 8, 16, 55, 21, tzinfo=timezone(timedelta(days=-1, seconds=61200))), last_datetime=datetime(2023, 6, 8, 16, 55, 21, tzinfo=timezone(timedelta(days=-1, seconds=61200)))),
            SenderSummary(from_='0.0.0.batamproject.com', count=1, first_datetime=datetime(2023, 9, 11, 23, 6, 47, tzinfo=timezone(timedelta(days=-1, seconds=75600))), last_datetime=datetime(2023, 9, 11, 23, 6, 47, tzinfo=timezone(timedelta(days=-1, seconds=75600)))),
            SenderSummary(from_='capitolmedicalclinic.com', count=1, first_datetime=datetime(2026, 2, 8, 16, 2, 27, tzinfo=timezone(timedelta(days=-1, seconds=68400))), last_datetime=datetime(2026, 2, 8, 16, 2, 27, tzinfo=timezone(timedelta(days=-1, seconds=68400)))),
            SenderSummary(from_='livinghelha.ru.com', count=1, first_datetime=datetime(2022, 9, 3, 2, 16, 6, tzinfo=timezone(timedelta(days=-1, seconds=61200))), last_datetime=datetime(2022, 9, 3, 2, 16, 6, tzinfo=timezone(timedelta(days=-1, seconds=61200)))),
            SenderSummary(from_='xxdlife.com', count=2, first_datetime=datetime(2022, 9, 16, 9, 49, 17, tzinfo=timezone(timedelta(seconds=3600))), last_datetime=datetime(2022, 10, 1, 16, 46, 38, tzinfo=timezone(timedelta(days=-1, seconds=61200)))),
            SenderSummary(from_='utp.edu.pe', count=1, first_datetime=datetime(2024, 12, 27, 10, 39, 2, tzinfo=timezone.utc), last_datetime=datetime(2024, 12, 27, 10, 39, 2, tzinfo=timezone.utc)),
            SenderSummary(from_='utp.edu.pe', count=1, first_datetime=datetime(2024, 11, 27, 9, 43, 20, tzinfo=timezone.utc), last_datetime=datetime(2024, 11, 27, 9, 43, 20, tzinfo=timezone.utc)),
            ]     
        summaries = {}
        for summary in list:
            summaries[summary.from_] = summary
        return summaries
    
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
        if not self.mailbox:
            self.connect()
        return self.mailbox.uids(self.getCrieria(from_, age))
    
    def delete_uids(self, uids: Sequence[str], bulk = DEFAULT_BULK_SIZE) -> Iterable:
        if not self.mailbox:
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
        if not self.mailbox:
            self.connect()
        archived = []
        if self.dry_run:
                logger.info(f"DRY RUN: Would archive {len(uids)} emails in batches of {bulk} ...")
        else:
            logger.info(f"Archiving {len(uids)} emails in batches of {bulk} ...")
            archived = self.mailbox.move(uids, "Archive", chunks=bulk)
        return archived

    def print_all_uids(self, uids: Sequence[str], bulk = DEFAULT_BULK_SIZE) -> None:
        if not self.mailbox:
            self.connect()
        for message in self.fetch_uids(uids, mark_seen=False, headers_only=False, bulk=bulk):
            print(message)

    def print_headers_uids(self, uids: Sequence[str], bulk = DEFAULT_BULK_SIZE) -> None:
        if not self.mailbox:
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
        #summaries = self.manager.fetch_domain_summaries()
        #summaries = self.manager.fetch_domain_summaries_mock()
        summaries = self.manager.fetch_summaries()
        #summaries = self.manager.fetch_summaries_mock()
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
    main()