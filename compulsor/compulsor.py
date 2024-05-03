import http.client
import logging
import os.path
import stat
from functools import cached_property

import click
import yaml
from jira import JIRA

from .discourse import CanDiscourseClient
from .formatting import sprintinfo, stripinfo


class Context:
    def __init__(self, config, debug=False):
        jconfig = config["services"]["jira"]
        self.jira = JIRA(
            config["services"]["jira"]["url"],
            basic_auth=(jconfig["username"], jconfig["token"]),
        )

        self.toolconfig = config["tools"]["compulsor"]
        self.serviceconfig = config["services"]
        self.debug = debug

        if debug:
            logging.basicConfig()
            logging.getLogger().setLevel(logging.DEBUG)
            requests_log = logging.getLogger("requests.packages.urllib3")
            requests_log.setLevel(logging.DEBUG)
            requests_log.propagate = True
            http.client.HTTPConnection.debuglevel = 1

    @cached_property
    def sprints(self):
        return self.jira.sprints_by_name(self.toolconfig["board"])


@click.group()
@click.option("--debug", is_flag=True, default=False, help="Enable debugging")
@click.option("--config", default="~/.canonicalrc", help="Config file location.")
@click.pass_context
def main(ctx, debug, config):
    ctx.ensure_object(dict)

    configpath = os.path.expanduser(config)

    # Check if the config file is locked to mode 600. Add a loophole in case it is being passed in
    # via pipe, it appears on macOS the pipes are mode 660 instead.
    statinfo = os.stat(configpath, dir_fd=None, follow_symlinks=True)
    if (statinfo.st_mode & (stat.S_IROTH | stat.S_IRGRP)) != 0 and not stat.S_ISFIFO(
        statinfo.st_mode
    ):
        raise click.ClickException(f"Credentials file {config} is not chmod 600")

    with open(configpath) as fd:
        config = yaml.safe_load(fd)

    if not config:
        raise click.ClickException(f"Could not load config file {configpath}")

    ctx.obj = Context(config, debug)


@main.command(help="Display a formatted pulse report")
@click.argument("pulse", nargs=-1)
@click.option("-k", "--keys", is_flag=True, help="Show Jira keys in the report")
@click.option("-p", "--private", is_flag=True, help="Show private items in the report")
@click.pass_obj
def showpulse(ctx, pulse, keys, private):
    if not len(pulse):
        pulse = ["latest"]

    click.echo(
        "\n".join(
            map(
                lambda sprintid: sprintinfo(
                    ctx,
                    sprintid,
                    keys,
                    reportnamefield=ctx.toolconfig["reportfield"],
                    showprivate=private,
                ),
                pulse,
            )
        )
    )


@main.command(help="Post pulse reports to discourse")
@click.argument("pulses", nargs=-1)
@click.option(
    "-d",
    "--discourse",
    "discourses",
    multiple=True,
    help="Discourses to post to. Omit for all configured discourses",
)
@click.option("-f", "--force", is_flag=True, help="Don't prompt to post")
@click.pass_obj
def postpulse(ctx, discourses, pulses, force):
    if not len(discourses):
        discourses = ctx.toolconfig["discourse"].keys()

    for pulse in pulses:
        # Start with the most complete version and strip it. This way we only need to edit once.
        info = sprintinfo(
            ctx,
            pulse,
            keys=True,
            reportnamefield=ctx.toolconfig["reportfield"],
            showprivate=True,
        )
        info = click.edit(info)

        if not info.startswith("## Pulse"):
            raise click.ClickException("Error: Text is invalid, bailing out")

        for discourse in discourses:
            keys = ctx.toolconfig["discourse"][discourse]["keys"]
            topic = ctx.toolconfig["discourse"][discourse]["topic"]
            showprivate = ctx.toolconfig["discourse"][discourse].get("private", False)
            url = ctx.serviceconfig["discourse"][discourse]["url"]

            client = CanDiscourseClient(ctx.serviceconfig["discourse"][discourse])

            content = stripinfo(info, private=showprivate, keys=keys)

            if not force:
                click.echo(f"Will post the content to {url}:")
                click.echo(content)
            if force or click.confirm("Ready to post?"):
                res = client.create_post(topic_id=topic, content=content)
                click.echo(
                    f'{ctx.serviceconfig["discourse"][discourse]["url"]}/t/{res["topic_slug"]}/{res["topic_id"]}/{res["post_number"]}'
                )


@main.command(help="Show discourse links")
@click.argument("discourses", nargs=-1)
@click.option("-t", "--test", is_flag=True, help="Ensure API keys are working")
@click.pass_obj
def showlinks(ctx, discourses, test):
    if not len(discourses):
        discourses = ctx.toolconfig["discourse"].keys()

    for discourse in discourses:
        topic = ctx.toolconfig["discourse"][discourse]["topic"]
        click.echo(f'{ctx.serviceconfig["discourse"][discourse]["url"]}/t/{topic}')

        if test:
            client = CanDiscourseClient(ctx.serviceconfig["discourse"][discourse])
            topic = client.posts(topic)


if __name__ == "__main__":
    main()
