from datetime import datetime, timedelta
import math

def datetime_day_range(middle_dt, for_sqlite_between=False):
	start_date = middle_dt.replace(hour=0, minute=0, second=0, microsecond=0)
	end_date = start_date + timedelta(1) - timedelta(seconds=1)
	if for_sqlite_between:
		return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
	return start_date, end_date

def datetime_week_range(middle_dt, for_sqlite_between=False):
	year, week, dow = middle_dt.isocalendar()
	start_date = middle_dt - timedelta(dow)
	start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
	end_date = start_date + timedelta(7) - timedelta(seconds=1)
	if for_sqlite_between:
		return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
	return start_date, end_date 

def datetime_month_range(middle_dt, for_sqlite_between=False):
	start_date = middle_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
	end_date = start_date.replace(month=start_date.month+1) - timedelta(microseconds=1)
	if for_sqlite_between:
		return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
	return start_date, end_date

def datetime_quarter_range(middle_dt, for_sqlite_between=False):
	quarter = int(math.ceil(float(7)/3))
	start_date = middle_dt.replace(day=1, hour=0, month=3*(quarter-1), minute=0, second=0, microsecond=0)
	end_date = middle_dt.replace(day=1, hour=0, month=3*(quarter), minute=0, second=0, microsecond=0)- timedelta(microseconds=1)
	if for_sqlite_between:
		return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
	return start_date, end_date

def datetime_year_range(middle_dt, for_sqlite_between=False):
	start_date = middle_dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
	end_date = start_date.replace(month=12) - timedelta(microseconds=1)
	if for_sqlite_between:
		return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
	return start_date, end_date

def datetime_day_within(middle_dt, for_sqlite_between=False):
	start_date = middle_dt - timedelta(1)
	end_date = middle_dt + timedelta(1)
	if for_sqlite_between:
		return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
	return start_date, end_date

def datetime_week_within(middle_dt, for_sqlite_between=False):
	middle_dt = middle_dt.replace(hour=0, minute=0, second=0, microsecond=0)
	start_date = middle_dt - timedelta(7)
	end_date = middle_dt + timedelta(7) - timedelta(microseconds=1)
	if for_sqlite_between:
		return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
	return start_date, end_date

def datetime_month_within(middle_dt, for_sqlite_between=False):
	middle_dt = middle_dt.replace(hour=0, minute=0, second=0, microsecond=0)
	start_date = middle_dt - timedelta(30)
	end_date = middle_dt + timedelta(30) - timedelta(microseconds=1)
	if for_sqlite_between:
		return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
	return start_date, end_date

def datetime_quarter_within(middle_dt, for_sqlite_between=False):
	middle_dt = middle_dt.replace(hour=0, minute=0, second=0, microsecond=0)
	start_date = middle_dt - timedelta(90)
	end_date = middle_dt + timedelta(90) - timedelta(microseconds=1)
	if for_sqlite_between:
		return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
	return start_date, end_date

def datetime_year_within(middle_dt, for_sqlite_between=False):
	middle_dt = middle_dt.replace(hour=0, minute=0, second=0, microsecond=0)
	start_date = middle_dt - timedelta(365)
	end_date = middle_dt + timedelta(365) - timedelta(microseconds=1)
	if for_sqlite_between:
		return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
	return start_date, end_date

if __name__ == "__main__":
	now = datetime.now()

	funcs = [
		datetime_day_range,
		datetime_day_within,
		datetime_week_range,
		datetime_week_within,
		datetime_month_range,
		datetime_month_within,
		datetime_quarter_range,
		datetime_quarter_within,
		datetime_year_range,
		datetime_year_within
	]

	for func in funcs:
		print '%s(%s)' % (func.__name__, now)
		print '> %s - %s' % func(now)
		print '%s(%s, for_sqlite_between=True)' % (func.__name__, now)
		print '> %s - %s' % func(now, True)
		print
