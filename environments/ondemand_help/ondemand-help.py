import sys
import os
import argparse

from botocore.exceptions import ClientError, NoCredentialsError

__SUBCOMMAND_TO_KEY = {
    'install-isce3': 'ondemand-test/install-isce3.py',
    'install-mintpy_ariatools': 'ondemand-test/install-mintpy_ariatools.py',
    'install-qed': 'ondemand-test/install-qed.py',
}

try:  # TODO: remove this outer try-except once stdin is working
    # Do not enclose this in a main as this code will be ran via exec()
    __remote_parser = argparse.ArgumentParser(
        prog='ondemand-help',
        description="OnDemand help script, provides various utilities for the OnDemand system.",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False
    )
    __remote_parser.add_argument(
        '--help', '-h',
        action='store_true',
        help="Show this help message and exit. If command is specified, show help for that command."
    )
    __remote_parser.add_argument(
        'command',
        nargs='?',
        default=None,
        help=f"The command to execute for the help script. Available subcommands:{''.join(f'\n - {sc}' for sc in __SUBCOMMAND_TO_KEY)}"
    )

    if len(sys.argv) == 1:
        __remote_parser.print_help()
        sys.exit(0)
    
    __remote_args, __subcommand_args = __remote_parser.parse_known_args()

    if __remote_args.command is None:
        __remote_parser.print_help()
        sys.exit(0)
    if __remote_args.help:
        __subcommand_args.insert(0, '--help')
    
    if __remote_args.command not in __SUBCOMMAND_TO_KEY:
        print(f"Subcommand '{__remote_args.command}' is not recognized.", file=sys.stderr)
        print(f"Available subcommands: {', '.join(__SUBCOMMAND_TO_KEY.keys())}", file=sys.stderr)
        sys.exit(1)
    try:
        # The double underscores in /opt/bin/ondemand-help.py don't actually mangle variable names from exec's perspective.
        subcommand_key = __SUBCOMMAND_TO_KEY[__remote_args.command]
        subcommand_filename = os.path.join(__dirpath, 'subcommand.py')
        __client.download_file(Bucket=__code_bucket, Key=subcommand_key, Filename=subcommand_filename)
        with open(subcommand_filename) as subcommand_fp:
            exec(subcommand_fp.read(), {'_HELP__ARGS': __subcommand_args, '_HELP__CLIENT': __client, '_HELP__BUCKET': __code_bucket, '_HELP__DIR': __dirpath})
    except NoCredentialsError as __remote_exception:
        # In theory, credentials could become invalid sometime between the two calls to download_file
        print("ERROR: Unable to connect to AWS, invalid credentials or none present.", file=sys.stderr)
        sys.exit(1)
    except ClientError as __remote_exception:
        print(f"ERROR: Failed to download file from AWS.\n{__remote_exception}", file=sys.stderr)
        sys.exit(1)
    except Exception as __remote_exception:
        print(f"ERROR: {__remote_exception}", file=sys.stderr)
        sys.exit(1)
except SystemExit:
    sys.exit(0)

