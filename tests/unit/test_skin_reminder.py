import json
from pathlib import Path
import subprocess


def test_reminder_calendar_has_real_alarm_neutral_fields_and_four_calendar_weeks(tmp_path):
    root=Path(__file__).resolve().parents[2]
    script=r"""
const fs=require('fs'),ts=require('typescript'),assert=require('assert');
const dir=JSON.parse(fs.readFileSync(0,'utf8')).dir;
for(const name of ['attuneMode','skinReminder'])fs.writeFileSync(dir+'/'+name+'.js',ts.transpileModule(fs.readFileSync('apps/vehicle-app/src/utils/'+name+'.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText);
const reminder=require(dir+'/skinReminder.js');
const now=new Date('2026-10-02T10:00:00+02:00'),due=reminder.defaultReminderDate(now);
assert.equal(due.getDate(),30);assert.equal(due.getHours(),now.getHours());
const calendar=reminder.buildReminderCalendar({id:'test-123',dueAt:'2026-10-30T10:00:00Z'});
assert(calendar.includes('DTSTART:20261030T100000Z\r\n'));
assert(calendar.includes('UID:test-123@attune.local\r\n'));
assert(calendar.includes('BEGIN:VALARM\r\nTRIGGER:PT0M\r\nACTION:DISPLAY'));
for(const sensitive of ['skin','mental','stress','cilt','hasta'])assert(!calendar.toLowerCase().includes(sensitive));
assert.throws(()=>reminder.buildReminderCalendar({id:'bad\r\nSUMMARY:injected',dueAt:'2026-10-30T10:00:00Z'}));
assert.throws(()=>reminder.buildReminderCalendar({id:'safe',dueAt:'invalid'}));
// Controlled storage fixture exercises real helpers, including failure propagation.
const storage=new Map(); let events=0;
global.localStorage={getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)};
global.window={location:{search:''},dispatchEvent:()=>{events++;}};
const future=new Date(Date.now()+86400000),first=reminder.saveSkinReminder(future);
assert.equal(reminder.saveSkinReminder(new Date(future.getTime()+3600000)).id,first.id);
assert.equal(storage.size,1);assert.equal(events,2);
const originalSet=localStorage.setItem;
localStorage.setItem=()=>{throw new Error('Controlled quota failure');};
assert.throws(()=>reminder.saveSkinReminder(future),/quota/);assert.equal(events,2);
localStorage.setItem=originalSet;
assert.throws(()=>reminder.saveSkinReminder(new Date(0)));assert.equal(events,2);
reminder.cancelSkinReminder();assert.equal(reminder.readSkinReminder(),null);assert.equal(events,3);
window.location.search='?demo=1';assert.throws(()=>reminder.saveSkinReminder(future),/Demo/);
assert.equal(storage.size,0);
"""
    subprocess.run(['node','-e',script],cwd=root,check=True,input=json.dumps({'dir':str(tmp_path).replace('\\','/')}),text=True,encoding='utf-8')
