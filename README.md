# MailTidy
**MailTidy** enables the cleanup of an IMAP mail account by deleteting the accumulated dross while retaining relevant mails.

Much received mail, which while not spam, ceases to be revelant over time. Best practise is to delete these in a timely manner, but who does? Instead accounts become cluttered with irrelevant emails, many never read, until their volumes become too onerous to tidy manually.

Enter **MailTidy**, which creates a summary for each unique sender domain or each unique sender and allows an action to be performed against each summary. These actions can be filtered by age. For example, to delete mails received from the domain `somewhere.com` or the unique sender `someone@somewhere.com` older than 365 days the DELETE action is specified with an age of 365. 

> **NOTE:** As of now **MailTidy** has been tested on `*nix` derivative operating systems such as `Linux` and `macOS`. While it should work fine on `Windows` without code changes the following instructions may reuire adjustement. Contributions welcome.

## Installation
**MailTidy** can be installed from the PyPi repository or be built and installed from source.

### Installation from the PyPi Repository

TBC

### Installation from Source
   1. Python Poetry is used to build, install and publish **MailTidy**. If not already installed, [follow these instructions](https://python-poetry.org/docs/#installation)
   2. Clone the source code from GitHub ??? URL ???
   3. From the project's root directory execute `poetry install` to build and install the **MailTidy** module. 

### Configure the IMAP account
    
The account details are stored in the YAML formatted file `connection_data.yml` located in the directory `$HOME/.mailtidy`. The format of the file is:

  ```yaml
  imap_server: <imap server address>
  port: <imap server port>
  email: <email address>
  password: <imap server password>
  ```
    
  For example:
  ```yaml
  imap_server: imap.provider.com 
  port: 993
  email: myaccount@myproveider.com
  password: mysecret
  ```

  > **IMPORTANT:** Secure the credentials stored within `connection_data.yml` by restricting acesss the owner by executing the command `chmod 600 ~/.mail_tidy/connection_data.yml` 

## Workflow Overview
The **MailTidy** workflow consists of the following steps:
1. Create summaries by executing `python mailtidy summarise` 
    
    This creates a YAML formatted file containing entries for each sender in the configured IMAP account. By default summaries are created for each unique sender domain. Use the `-u` option to create a summary for each unique sender.
    
    By default, summaries are written to the file `summaries.yml` in the current directory. Use the `-f` option to specify an alternate location.

    Each summary is created with the default action of NONE and an age of 0. If applied, no changes will occur.

2. It can take some time to summarise accounts with a large number of mails. Once done it is recommended that the produced `summaries.yml` file is copied to avoid the need to run a summary repeatedly while experimenting with the options.
3. Having created a copy of `summaries.yml` file edit the original to ammend the required Actions and ages. Initially, you may wish to process just a subset of the senders. To do simply leave the summaries for those you do not wish to process alone.
4. Apply the Actions by executing `python mailtidy apply`
   1. Dry runs are supported and recommended prior to making destructive changes. Specify `-n` or `--dry-run` on the command line. 

## Summaries
A **MailTidy** summary contains:
- The mail address of the sender
  - This may be the full email of the sender - `someone@somewhere.com` - or the domain name - `somewhere.com`
- The number of mails received from the sender
- The UTC first date and time a mail from the sender was received  
- The UTC last date and time a mail from the sender was received 
  
Additionally, the summary contains the following fields that describe the action to be applied 
- The action to be taken, default = `'none'`  
- The age in days below which the Action is performed, default = `0`
  
**MailTidy** summaries are serialised in a YAML formatted file using the following format:
```yaml
- !SenderSummary
  action: !Action 'none'
  age: 0
  count: 68
  first_datetime: 2023-03-18 19:03:03+01:00
  from_: 'someone@somewhere.com'
  last_datetime: 2023-03-18 19:03:03+01:00
```
The YAML file may use anchors (`&`) and aliases (`*`) to abbreviate these definitions. For example, the following defines the `NONE` action and then references its definition:
```yaml
- !SenderSummary
  action: &id001 !Action 'none'
  age: 0
  count: 68
  first_datetime: 2023-03-18 19:03:03+01:00
  from_: 'someone@somewhere.com'
  last_datetime: 2023-03-18 19:03:03+01:00
- !SenderSummary
  action: *id001
  age: 0
  count: 1
  first_datetime: 2023-03-18 19:03:03+01:00
  from_: 'someoneelse@elseswhere.com'
  last_datetime: 2023-03-18 19:03:03+01:00
```

### Supported Actions
**MailTidy** supports the following Actions, each of which is applied to mails from the sender younger than the specified age:

The below lists the supported Python Action enumeration, the action performed and their YAML equivalants...  

- Action.NONE
  - No processing is applied
  - `!Action 'none'`
- Action.DELETE
  - Delete the selected mails
  - `!Action 'delete'`
- Action.ARCHIVE
  - Move the selected mails to the `Archive` folder
  - `!Action 'archive'`
- Action.PRINT_ALL
  - Print the entire content of the selected emails to `stdout` 
  - `!Action 'print_all'`
- Action.PRINT_HEADERS
  - Print the headers of the selected emails to `stdout`
  - `!Action 'print_headers'`

## Future
There are many features that might be added to **MailTidy**. 

Amongst which are filters on mail status, such as ```answered``` to retain converstaions regardless of their age.  

But don't hold your breath as **MailTidy** is not a priority project for me. Just something I required to cleanup multiple mail accounts I'd neglected for far too long. 

Something I have chosen to publish should it be of help to others. 

Ideas are welcome, especially so if backed by code contibutions 😏. 