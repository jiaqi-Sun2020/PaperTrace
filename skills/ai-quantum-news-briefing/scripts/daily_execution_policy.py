"""Automatic date selection only; never relabel a historical publication."""
from datetime import date,timedelta

AUTOMATIC_RELEASE_NOT_BEFORE='2026-10-16'
TIMEZONE='Asia/Shanghai'

def release_date(value):
    if not isinstance(value,str) or date.fromisoformat(value).isoformat()!=value:
        raise ValueError('release_date_invalid')
    return date.fromisoformat(value)

def execution_window(day):
    release=release_date(day)
    return {'date':day,'coverage_date':(release-timedelta(days=1)).isoformat(),
            'timezone':TIMEZONE,'automatic_release_not_before':AUTOMATIC_RELEASE_NOT_BEFORE,
            'execution_scope':'requested_date_only'}

def retired(day,*,not_before=None):
    return release_date(day)<release_date(not_before or AUTOMATIC_RELEASE_NOT_BEFORE)

def retired_state(day):
    return {**execution_window(day),'status':'historical_retired','phase':'historical_retired',
            'run_outcome':'not_scheduled','action_required':False,'publication_approved':False,
            'execution_order':[],'next_date':None,'final_response_allowed':True,'terminal_blocker':None,
            'next_action':'History retained; automatic backfill is retired. Do not collect, generate or publish this date.'}
