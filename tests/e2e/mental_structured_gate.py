"""Opt-in real-app gate smoke. Real local API, synthetic ASR; no physical audio.

Run a frontend built/started with NEXT_PUBLIC_MENTAL_CONVERSATION_ENGINE=structured-v1
and the API with ATTUNE_MENTAL_STRUCTURED_ENABLED=1. The checked-in unapproved
library must block ordinary replies, while local crisis handling retains priority.
"""
import json
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    origin=os.getenv('MENTAL_TEST_ORIGIN','http://127.0.0.1:3000')
    chrome=os.getenv('MENTAL_TEST_CHROME','/workspace/.attune-tools/chrome/opt/google/chrome/chrome')
    results=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=chrome,headless=True,args=['--mute-audio'])
        for text,crisis in [('I lost my job yesterday and I feel sad.',False),('I want to kill myself',True)]:
            context=browser.new_context()
            context.add_init_script("""
              localStorage.setItem('attune.language.v1','en');
              localStorage.setItem('attune_health_processing_v1',JSON.stringify({version:1,services:{mental:{at:'2026-10-27T00:00:00Z',permissions:['recognition','conversation','speech-output-v2']}}}));
              localStorage.setItem('togg_privacy_mental_summary_allowed','false');
              window.attuneOutputMuted=true;
              class Recognition {start(){window.probeRecognition=this;this.onstart?.()}abort(){this.onend?.()}}
              window.SpeechRecognition=Recognition;
            """)
            page=context.new_page();requests=[]
            page.on('request',lambda request:requests.append(request.url) if '/api/mental' in request.url else None)
            page.goto(origin+'/mental')
            history=page.get_by_label('I allow OpenAI to process relevant previous session summaries for this summary.',exact=True)
            expect(history).to_be_visible(timeout=20000);expect(history).not_to_be_checked()
            start=page.get_by_role('button',name=re.compile('^start conversation$',re.I))
            expect(start).to_be_enabled(timeout=20000);start.click()
            page.wait_for_function('Boolean(window.probeRecognition?.onresult)')
            page.evaluate("text=>window.probeRecognition.onresult({resultIndex:0,results:[Object.assign([{transcript:text}],{isFinal:true})]})",text)
            if crisis:
                expect(page.locator('[data-chat-author="AI"]').filter(has_text='112').first).to_be_visible()
                assert not any('/converse' in url for url in requests)
            else:
                expect(page.get_by_text('The prepared conversation is not available yet; content and audio review are required.',exact=True)).to_be_visible()
                assert sum('/converse' in url for url in requests)==1
            assert not any('/speech' in url or '/analyze-session' in url or '/compact-context' in url for url in requests)
            assert page.locator('[data-mental-current-summary]').count()==0
            results.append({'scenario':'crisis' if crisis else 'unapproved-library','passed':True,'generationRequests':0})
            context.close()
        browser.close()
    print(json.dumps({'realLocalAPI':True,'syntheticASR':True,'physicalAudioTested':False,'results':results},indent=2))


if __name__=='__main__':main()
