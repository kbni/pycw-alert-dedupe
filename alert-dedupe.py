import pycw
import simplejson
import os
import re
import random
import traceback
import email
import time
import datetime
import sqlite3
import dateranges

class AlertDedupe(pycw.Scaffold):
	macros = {}
	rules = []

	test_emails = []
	config_cache = []

	search_boards = []
	search_status = [ 'SilentNew', 'New' ]
	search_limit = 0
	date_crit = 'within-month'
	include_previous = 0
	reopen_tickets = 1

	status_new = 'New (dedupe)'
	status_close = 'Closed (dedupe)'
	status_reopen = 'Reopen (dedupe)'
	fake_receiver = 'alerts@example.com'
	config_not_matched = 'Could not find the config..'
	last_ticket = None

	def __init__(self):
		pycw.Scaffold.__init__(self)
		self.add_argument('--loop', action='store_true', dest='loop')
		self.add_argument('--once', action='store_true', dest='once')
		self.add_argument('--test-shell', action='store_true', dest='test_shell')
		self.add_argument('--rules-file', action='store', dest='rules_file', default='./rules.json')
		self.add_argument('--data-file', action='store', dest='data_file', default='./history.db')
		self.add_argument('--debug-rules', action='store_true', dest='debug_rules')
		self.add_argument('--debug-regex', action='store_true', dest='debug_regex')
		self.add_argument('--debug-sql', action='store_true', dest='debug_sql')
		self.add_argument('--test-search-configs', action='store_true', dest='test_search_configs')
		self.add_argument('--create-test-tickets', action='store_true', dest='create_test_tickets')

	def loop(self):
		self.parse_rules_file()

		self.dbconn = sqlite3.connect(self.args.data_file)

		self.sql_create_table()

		if self.args.test_shell:
			self.shell(locals())
			return

		if self.args.create_test_tickets:
			self.create_test_tickets()
		self.test_emails = None

		while self.args.loop:
			self.check_board()

		if self.args.once:
			self.check_board()

	def check_board(self):
		for ticket in self.search_tickets():
			self.last_ticket = ticket
			ret_vars = self.find_rule(ticket)

			if ret_vars and ret_vars.has_key('rule'):
				if not ret_vars.has_key('company'):
					self.info('No company detected for %s (configurations not matching?)' % ticket)
					continue

				rule = ret_vars['rule']
				orig_ticket = ret_vars['ticket']
				company = ret_vars['company'].CompanyIdentifier

				use_ticket = None
				original_dedupe = self.sql_find_original(rule, ret_vars)

				if original_dedupe:
					try:
						use_ticket = self.cw.ServiceTicket(original_dedupe)
					except pycw.CWObjectNotFound:
						self.warning('Stale ticket #%s in history - ticket deleted?' % original_dedupe)

					if use_ticket and use_ticket.ClosedFlag:
						if rule.reopen_tickets:
							use_ticket.data.StatusName = ret_vars.get('status_reopen', rule.status_reopen)
							self.debug('Reopening %s (status: %s)' % (use_ticket, use_ticket.data.StatusName))
						else:
							self.debug('Not reopening existing ticket %s' % use_ticket)
							use_ticket = None

				if not use_ticket:
					use_ticket = self.cw.ServiceTicket()
					use_ticket.data.Board = ret_vars.get('service_board', orig_ticket.Board)
					use_ticket.data.CompanyId = int(ret_vars['company'].record_id)
					use_ticket.data.CompanyIdentifier = ret_vars['company'].CompanyIdentifier
					use_ticket.data.StatusName = ret_vars.get('status_new', rule.status_new)

					new_summary = rule.new_ticket_summary
					for try_eval in re.findall('\\${(.+?)}', new_summary):
						try:
							new_summary = new_summary.replace('${%s}'%try_eval, eval(try_eval, None, ret_vars))
						except:
							self.error('Eval error: %s' % try_eval)
							continue
					use_ticket.data.Summary = new_summary

				for config in ret_vars['configs']:
					use_ticket.assoc_configuration(config)
					
				use_ticket.save()

				orig_ticket.data.StatusName = ret_vars.get('status_close', rule.status_close)
				orig_ticket.save()
				self.debug('Closing %s (status: %s)' % (orig_ticket, orig_ticket.data.StatusName))

				note = self.cw.TicketNote(parent=orig_ticket)
				note.data.NoteText = 'Ticket closed, please refer:\n#%06d - %s' % ( use_ticket.record_id, use_ticket.Summary )
				note.data.DateCreated = datetime.datetime.now().isoformat()
				note.data.IsInternalNote = False
				note.data.IsExternalNote = True
				note.data.IsPartOfDetailDescription = True
				note.data.IsPartOfInternalAnalysis = False
				note.data.IsPartOfResolution = False
				note.save()

				self.sql_store_original(
					orig_ticket.EnteredDate, orig_ticket.record_id, orig_ticket.Summary,
					use_ticket.record_id, use_ticket.Summary,
					ret_vars['company'].record_id, rule.rule_id, rule.subject_id
				)


	def sql_create_table(self):
		curs = self.dbconn.cursor()

		create_history_table = """
		CREATE TABLE IF NOT EXISTS history (
			ts TIMESTAMP,
			orig_ticket_id INTEGER,
			orig_ticket_summary STRING,
			new_ticket_id INTEGER,
			new_ticket_summary STRING,
			company_id INTEGER,
			rule_id STRING,
			subject_id STRING)
		"""

		curs.execute(create_history_table)

	def sql_store_original(self, ts, orig_ticket_id, orig_ticket_summary, new_ticket_id, new_ticket_summary, company_id, rule_id, subject_id):
		args = ts, orig_ticket_id, new_ticket_id, orig_ticket_summary, new_ticket_summary, company_id, rule_id, subject_id
		sql_query = "INSERT INTO history (ts, orig_ticket_id, new_ticket_id, orig_ticket_summary, new_ticket_summary, company_id, rule_id, subject_id) VALUES (%s)" % ','.join(['?']*len(args))
		if self.args.debug_sql:
			self.debug('%s %s' % (sql_query, args))
		curs = self.dbconn.cursor()
		curs.execute(sql_query, args)
		self.dbconn.commit()

	def sql_find_original(self, rule, ret_vars):
		curs = self.dbconn.cursor()

		conditions = [
			'rule_id = "%s"' % rule.rule_id,
			'company_id = %d' % int(ret_vars['company'].record_id)
		]

		func_map = {
			'same-week': dateranges.datetime_week_range,
			'same-month': dateranges.datetime_month_range,
			'same-quarter': dateranges.datetime_quarter_range,
			'same-year': dateranges.datetime_year_range,
			'within-week': dateranges.datetime_week_range,
			'within-month': dateranges.datetime_month_range,
			'within-quarter': dateranges.datetime_quarter_range,
			'within-year': dateranges.datetime_year_range
		}

		for date_crit, func in func_map.iteritems():
			if date_crit == rule.date_crit:
				start_date, end_date = func(ret_vars['ticket'].EnteredDate, True)
				conditions.append("strftime('%%Y-%%m-%%d',ts) BETWEEN '%s' and '%s'" % (start_date, end_date))
				break

		sql_query = "SELECT new_ticket_id FROM history WHERE %s ORDER BY ts DESC" % ' AND '.join(conditions)

		if self.args.debug_sql:
			self.debug('sql_find_original: %s' % sql_query)

		for row in curs.execute(sql_query):
			return row[0]

		return None

	def create_test_tickets(self, destination_board = False):
		if not destination_board:
			destination_board = self.search_boards[0]

		try:
			company = self.cw.search('Company', 'CompanyName = "Catchall"', 1)[0]
		except IndexError:
			self.fatal('You do not have a Catchall company?')

		for test in self.test_emails:
			test_email = "Subject: %s\nFrom: %s\nTo: %s\n\n%s\n" % ( test['subject'], test['sender'], self.fake_receiver, test['body'] )

			ticket = self.cw.ServiceTicket()
			ticket.Summary = test['subject']
			ticket.Board = destination_board
			ticket.CompanyId = company.record_id
			ticket.CompanyIdentifier = company.CompanyIdentifier
			ticket.StatusName = 'SilentNew'
			ticket.save()

			note = self.cw.TicketNote(parent=ticket)
			note.NoteText = test['body']
			note.CreatedBy = test['sender']
			note.DateCreated = ticket.EnteredDate.isoformat()
			note.IsInternalNote = False
			note.IsExternalNote = True
			note.IsPartOfDetailDescription = True
			note.IsPartOfInternalAnalysis = False
			note.IsPartOfResolution = False
			note.save()

			DocumentInfo = self.cw.caddy.ServiceTicket().factory.create('DocumentInfo')
			DocumentInfo.FileName = '[%s] test email.eml' % ticket.record_id
			DocumentInfo.Title = '%s' % test['subject']
			DocumentInfo.IsPublic = True
			DocumentInfo.Content = test_email.encode('base64','strict')

			ArrayOfDocumentInfo = self.cw.caddy.ServiceTicket().factory.create('ArrayOfDocumentInfo')
			ArrayOfDocumentInfo[0].append(DocumentInfo)

			self.cw.caddy.soap_call('ServiceTicket', 'AddTicketDocuments', ticket.record_id, ArrayOfDocumentInfo)

			self.info('Created ticket: %s / %s' % (ticket, DocumentInfo.FileName))

	def search_tickets(self):
		search_terms = ' And '.join([
			'ClosedFlag = false',
			'( %s )' % ' Or '.join([ 'BoardName = "%s"' % s for s in self.search_boards ]),
			'( %s )' % ' Or '.join([ 'StatusName = "%s"' % s for s in self.search_status ]),
		])

		if self.last_ticket is not None:
			search_terms = 'Id > %s And %s' % (self.last_ticket.record_id, search_terms)

		self.debug("Searching for %s tickets (Conditions: %s)" % (self.search_limit, search_terms))
		return self.cw.search('ServiceTicket', search_terms, limit = self.search_limit, orderby = 'Id')

	def find_config(self, config_name):
		results = []

		if config_name != "" and config_name is not None:
			search_terms = [
				'ClosedFlag = false And ConfigurationName = "%s"' % config_name,
				'ClosedFlag = false And ConfigurationName LIKE "%s (%%)"' % config_name
			]
			if '-ws-' in config_name or '-sv-' in config_name:
				search_terms.append('ClosedFlag = false And ConfigurationName LIKE "%s."')

			for search_term in search_terms:
				for config in self.cw.search('Configuration', search_term):
					if config not in results:
						results.append(config)

		if len(results) == 1:
			return results[0]
		else:
			return False

	def find_rule(self, test_object, only_rule = None, resolve_configs = True):
		amongst_rules = self.rules
		if only_rule:
			amongst_rules = [only_rule,]
		for rule in amongst_rules:
			ret_vars = dict( rule=rule, configs=[] )

			if rule.config_per_line:
				lines = self.get_object_notes(test_object)
				if lines:
					for line in lines.split('\n'):
						groupdict = self.match_groupdict(rule.config_per_line, line)
						if groupdict and groupdict.has_key('config_name'):
							ret_vars['configs'].append(groupdict['config_name']) 
							ret_vars['config_name'] = groupdict['config_name']
				else: continue

			if rule.match_ticket_summary is not None:
				groupdict = self.cmp_ticket_summary(rule, test_object)
				if groupdict: ret_vars.update(groupdict)
				else: continue

			if rule.match_ticket_notesby is not None:
				groupdict = self.cmp_ticket_notesby(rule, test_object)
				if groupdict: ret_vars.update(groupdict)
				else: continue

			if rule.match_ticket_notes is not None:
				groupdict = self.match_groupdict(rule, self.get_object_notes(test_object))
				if groupdict: ret_vars.update(groupdict)
				else: continue

			if resolve_configs and hasattr(test_object, 'record_id'):
				config_name = ret_vars.get('config_name', None)
				configs = []

				for config_name in ret_vars['configs']:
					config = self.find_config(config_name)
					if config:
						configs.append(config)
					else:
						self.error('Unable to resolve config_name: %s' % config_name)

				if config_name:
					config = self.find_config(config_name)
					if config:
						configs.append(config)
					else:
						self.error('Unable to resolve config_name: %s' % config_name)

				if configs:
					ret_vars['configs'] = configs
					ret_vars['company'] = self.cw.Company(configs[0].CompanyId)
				ret_vars['ticket'] = test_object

			return ret_vars # We've located our rule, return
		return None # Looks like we didn't succeed - oops!

	def match_groupdict(self, compiled_re, match_str):
		match = compiled_re.match(match_str)
		if match:
			return match.groupdict()
		else:
			if self.args.debug_regex:
				self.debug('could not match:\n  %s\n  %s' % ( compiled_re.pattern, match_str ))
			return False

	def get_object_notes(self, test_object):
		test_string = None
		if type(test_object) == dict:
			test_string = test_object['body']
		else:
			note = test_object.first_ticket_note()
			if note:
				test_string = note.NoteText
		return test_string

	def cmp_ticket_summary(self, rule, test_object):
		test_string = ''

		if type(test_object) == dict:
			test_string = test_object['subject']
		else:
			test_string = test_object.Summary
			if test_string.endswith('...'):
				email = test_object.get_original_email()
				if email:
					test_string = email['Subject'].replace('\r\n', '')
		
		return self.match_groupdict(rule.match_ticket_summary, test_string)

	def cmp_ticket_notesby(self, rule, test_object):
		test_string = ''

		if type(test_object) == dict:
			test_string = test_object['sender']
		else:
			note = test_object.first_ticket_note()
			if note:
				test_string = note.CreatedBy 

		return self.match_groupdict(rule.match_ticket_notesby, test_string)

	def parse_rules_file(self):
		if not os.path.exists(self.args.rules_file):
			self.fatal('Rules file does not exist: %s' % self.args.rules_file)

		with open(self.args.rules_file, 'r') as rules_fh:
			self.data = simplejson.load(rules_fh)

			for name, value in self.data['options'].iteritems():
				if hasattr(self, name):
					setattr(self, name, value)
				else:
					self.fatal('unknown option: %s' % name)

			for name, macro in self.data['macros'].iteritems():
				try:
					cre = re.compile(macro['re'], re.I)

					for test_string in macro.get('test_strings', []):
						matched = cre.match(test_string)
						if not matched:
							self.error('%s does not match test_string "%s"' % (macro['re'], test_string))
						elif self.args.debug_regex:
							self.debug('%s matched test_string "%s" with %s' % (macro['re'], test_string, matched.groupdict()))

					if self.error_count > 0:
						self.fatal('Problems with macro: %s' % name)
					else:
						if self.args.debug_rules:
							self.debug('Macro tested okay: %s' % name)

					self.macros[name] = macro

				except:
					self.error('Bad regex: %s' % macro['re'])

			for rule in self.data['rules']:
				for subject in rule['subjects']:
					subject_rule = dict()
					for k,v in rule.iteritems():
						if k not in ('name', 'subjects'):
							subject_rule[k]=v
					for k,v in subject.iteritems():
						if k != ('name', 'test_emails'):
							subject_rule[k]=v

					dr = DedupeRule(rule['name'], subject['name'], self, self.macros, **subject_rule)
					dr.tests = subject.get('test_emails', [])
					self.rules.append(dr)

		for test_company in self.data['test_companies']:
			for rule in self.rules:
				for test in rule.tests:
					test['is_fake'] = True

					servers = [ x for x in test_company['configs'] if 'server' in x ]
					routers = [ x for x in test_company['configs'] if 'router' in x ]
					workstations = [ x for x in test_company['configs'] if 'workstation' in x ]

					random.shuffle(servers)
					random.shuffle(routers)
					random.shuffle(workstations)

					if True:
						test['subject'] = test['subject'].replace('$company_domain', test_company['company_domain'])
						test['sender'] = test['sender'].replace('$company_domain', test_company['company_domain'])
						test['body'] = test['body'].replace('$company_domain', test_company['company_domain'])

					while '$random_server' in str(test):
						random_server = servers.pop()
						test['subject'] = test['subject'].replace('$random_server', random_server[0], 1)
						test['sender'] = test['sender'].replace('$random_server', random_server[0], 1)
						test['body'] = test['body'].replace('$random_server', random_server[0], 1)

					while '$random_router' in str(test):
						random_router = routers.pop()
						test['subject'] = test['subject'].replace('$random_router', random_router[0], 1)
						test['sender'] = test['sender'].replace('$random_router', random_router[0], 1)
						test['body'] = test['body'].replace('$random_router', random_router[0], 1)

					while '$random_workstation' in str(test):
						random_workstation = workstations.pop()
						test['subject'] = test['subject'].replace('$random_workstation', random_workstation[0], 1)
						test['sender'] = test['sender'].replace('$random_workstation', random_workstation[0], 1)
						test['body'] = test['body'].replace('$random_workstation', random_workstation[0], 1)

					ret_vars = self.find_rule(test, resolve_configs = False)
					self.test_emails.append(test)

					if ret_vars and ret_vars.get('rule', None) == rule:
						if self.args.debug_rules:
							self.debug('Matched expected rule %s' % rule)

						if self.args.test_search_configs and ret_vars.has_key('config_name'):
							config = self.find_config(ret_vars['config_name'])
							if config:
								self.debug('We even matched a configuration: %s, %s' % (config, config.ConfigurationName))
							else:
								self.debug('Unable to match config_name: %s' % ret_vars['config_name'])

					else:
						self.error('Expected to match %s' % rule)
						if self.args.debug_regex is False:
							self.args.debug_regex = True
							self.find_rule(test, rule)
							self.args.debug_regex = False

		if self.error_count > 0:
			self.fatal('Parsing the rules file resulted in some errors. Please fix the errors and try again.')

class DedupeRule(object):
	rule_id = None
	subject_id = None
	date_crit = None
	reopen_tickets = None

	status_new = None
	status_reopen = None
	status_close = None

	match_ticket_summary = None
	match_ticket_notesby = None
	match_ticket_notes = None
	config_per_line = False

	new_ticket_summary = None

	def __repr__(self):
		return '<DedupeRule(%s.%s)>' % (self.rule_id, self.subject_id)

	def __getattr__(self, attr_name):
		if hasattr(self.parent, attr_name):
			return getattr(self.parent, attr_name)
		raise AttributeError

	def __init__(self, rule_id, subject_id, parent, macros, **kwargs):
		self.rule_id = rule_id
		self.subject_id = subject_id
		self.parent = parent

		self.status_new = parent.status_new
		self.status_close = parent.status_close
		self.status_reopen = parent.status_reopen
		self.reopen_tickets = parent.reopen_tickets
		self.date_crit = parent.date_crit

		for k,v in kwargs.iteritems():
			setattr(self, k, v)

		for attr in dir(self):
			if attr.startswith('match_') or attr == 'config_per_line':
				full_regex = getattr(self, attr)
				if full_regex:
					for macro_name, macro_dict in macros.iteritems():
						full_regex = full_regex.replace('%'+macro_name+'%', macro_dict['re'])
					setattr(self, attr, re.compile(full_regex, re.I))

if __name__ == '__main__':
	AlertDedupe().run()
