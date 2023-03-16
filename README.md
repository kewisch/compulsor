compulsor
=========

This client application will help gather pulse reporting information from jira and post it to
discourse. It is very purpose-built and likely only useful if you are working at Canonical.

configuration
-------------

You need a `~/.canonicalrc` like so, it should be mode 600.

```yaml
services:
  jira:
    url: "https://warthogs.atlassian.net"
    username: "your_email"
    token: "your_jira_token"     # Get this from
  discourse:                     #   https://id.atlassian.com/manage-profile/security/api-tokens
    ubuntu:
      url: "https://discourse.ubuntu.com"
      username: "your_username"
      key: "your_token"          # You'll need an admin to get you one 
    canonical:
      url: "https://discourse.canonical.com"
      username: "your_username"
      key: "your_token"

tools:
  compulsor:
    project: "your_project_key"  # Your project key, e.g. CT
    board: your-sprint-board-id  # The id of your sprint board, see the URL when you are on it
    discourse:
      ubuntu:
        topic: 123               # the topic id to post to
        keys: false              # If true, jira keys will be included
      canonical:
        topic: 234
        keys: true
        private: true            # If private items should be shared
```

Installation and Use
--------------------

This project is using pipenv to manage dependencies, and requires python 3. Here is how to install and run:

```bash
$ pipenv install
$ pipenv run compulsor --help
Usage: compulsor.py [OPTIONS] COMMAND [ARGS]...

Options:
  --debug  Enable debugging

Commands:
  postpulse  Post pulse reports to discourse
  showpulse  Display a formatted pulse report

$ pipenv run compulsor showpulse --help
Usage: compulsor.py showpulse [OPTIONS] [PULSE]...

  Display a formatted pulse report

Options:
  -k, --keys  Show Jira keys in the report

$ pipenv run compulsor post pulse --help
Usage: compulsor.py postpulse [OPTIONS] [PULSE] [DISCOURSES]...

  Post pulse reports to discourse

Options:
  -a, --all  Post pulse report to all configured discourses
```  

Gathering Information
---------------------

On Jira, drop one of these this into the description or a comment:

```
PULSEDESC: I did a thing in the current sprint (uses comment date, best be more explicit)
PULSEDESC[2023#2]: I did a thing in this specific sprint
PULSEDESC[2023#5,private]: I did a thing in this sprint, and it should only be shared privately
```
