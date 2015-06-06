# alert-dedupe.py

Are the root causes to all your noisy alerts just a little evasive? Are you missing genuine problems because all of your level 1 technicians get a panic attack when they check the Service Board? This script might be for you.

## Features

 * Scans multiple Service Boards for duplicate tickets
 * Matches those tickets against macros (based on regular expressions)
 * Creates a master ticket with an IA note referencing those tickets
 * Master ticket can be reopened if closed - within timeframes
 * Master ticket can list previously matched tickets in Internal Analysis

## Giving it a test-run

1. Download the sourcecode (and [pycw](https://github.com/kbni/pycw) library this is based on)
2. In ConnectWise `Setup Tables > Service Board` create a new service board `Testing/Alerts` with the following Statuses `SilentNew`, `SilentClose`, `New (dedupe)`, `Closed (dedupe)`, `Reopened (dedupe)`
3. Make sure you have a `Catchall` company that is active (Service Tickets can be created against it) as well as two test companies (`Yellow Systems, L.L.C` and `Pink Networks, L.L.C`)
3. Check the `rules.json` file - make sure there are Configurations that match the name (the type in the file is just for generation of test ticket data, actual Configuration type is unimportant)
4. Run `python alert-dedupe.py --setup`, you'll want to follow the prompts and supply it with an Integrator Login (set this up in ConnectWise `Setup Tables >> Integrator Logins`)
5. Run `python alert-dedupe.py --create-test-tickets` to create some test tickets in ConnectWise on your new `Testing/Alerts` board.
6. Run it a few more times. Why not?
7. Run `python alert-dedupe.py --loop` to process all of those tickets. You can also run `python alert-dedupe.py --once` to process only a few of these.

What you should see when you run `--loop` or `--once` is the tickets are compacted, you know, except where a configuration is invalid. 

## How it works

1. Scans over Service Boards (`options[service_boards`) for tickets to process.
2. Matches these tickets using regular expressions (which return identifiable groups)
3. Using the regular expressions, creates a new ticket (ideally, more readable)
4. If that new ticket already exists, piles the duplicate onto the existing ticket
5. Closes the original ticket

## Adjusting the `rules.json` file

### Under `options`
* `reopen_tickets` if set to 1 a closed master ticket will be reopened if `date_crit` is met
* `date_crit` specifies within what time period, or what same time period to look for tickets for `reopen_tickets` (`within-year`, `within-quarter`, `same-month`, `same-week` etc)
* `include_previous` - how many entries (not matched to current master ticket) you would like to reference in Internal Analysis
* `search_limit` - how many tickets to search for at a time
* `status_new` - status used to create new master tickets
* `status_close` - status used to close duplicate tickets
* `status_reopen` - status used to reopen a closed master ticket
* `search_boards` - an array of boards to process
* `search_status` - an array of statuses to process

Some of the above can also be applied under `rules` which then apply for each `subject` beneath it.

## Stuff you might need

 * [pycw](https://github.com/kbni/pycw) - Python ConnectWise library
 * python-sqlite3 - for storing historical data
 * python-suds - required by pycw

## TODO (one day..)

* If a configuration does not match, leave a note in original alert ticket
* Email alerts for tickets, ability to adjust ticket Impact/Severity
* Better `--help`
* Cleanup of code

## Important Information

Code is offered without any form of warranty. You alone are liable for the data on your system.

No license is offered. Just be cool.

If you have any feedback, feel free to email them to me (alex -at- kbni -dot- net).

