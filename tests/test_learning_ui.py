"""Isolated UI components: no live service, accounts or external requests."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright
from formula_lab.pdf_export import chromium_executable


def test_assessment_resume_retry_summary_and_percentage_meter():
    static=Path(__file__).parents[1]/'formula_lab/static'
    harness='''<header class="app-header"></header><main></main><div data-generation-allowance></div>
    <script type="module">
    import {createReviewUI} from '/static/review-ui.js';
    import {createAllowanceUI} from '/static/allowance-ui.js';
    import {createRenameDialog} from '/static/rename-ui.js';
    const rounds=[],record={id:'d'.repeat(32),data:{mode:'flashcards',items:[{},{}]},itemIndex:0,flipped:false};
    window.fixture={record,rounds,fail:false,renamed:null};let ui;
    async function api(url,options){
      if(url==='/api/generation/allowance')return {limited:true,daily_tokens:200000,remaining_percent:75,resets_at:new Date(Date.now()+3600000).toISOString(),reserved_tokens:0};
      const body=JSON.parse(options.body);let round=rounds.at(-1);
      if(url.endsWith('/reviews')){
        if(!round||body.new_round){round={id:String(rounds.length).padStart(32,'a'),answers:[],answered_count:0,correct_count:0,item_count:2,completed_at:null,history:[]};rounds.push(round);}
      }else{
        if(window.fixture.fail){window.fixture.fail=false;throw new Error('Fixture connection interrupted');}
        if(window.fixture.conflict){window.fixture.conflict=false;round.answers.push({index:body.index,correct:!body.correct});round.answered_count=round.answers.length;const error=new Error('This card was rated on another device.');error.status=409;throw error;}
        if(!round.answers.some(a=>a.index===body.index))round.answers.push(body);
        round.answered_count=round.answers.length;round.correct_count=round.answers.filter(a=>a.correct).length;round.incorrect_count=round.answered_count-round.correct_count;round.score_percent=round.correct_count*50;
        if(round.answered_count===2){round.completed_at='2026-10-28T00:00:00Z';round.history=[{id:round.id,completed_at:round.completed_at,score_percent:round.score_percent}];}
      }
      return structuredClone(round);
    }
    function render(){const main=document.querySelector('main');main.replaceChildren();const summary=ui.summary(record);
      if(summary&&!record.reviewBrowse){main.append(summary);return;}
      const flip=document.createElement('button');flip.textContent='Flip';flip.onclick=()=>{record.flipped=!record.flipped;render();};
      const controls=ui.controls(record);controls.update(record.flipped);main.append(flip,controls.root);
    }
    const options={api,userId:'fixture',onChange:render,select:(r,i)=>{r.itemIndex=i;r.flipped=false;render();},onError:()=>{}};
    window.remount=()=>{ui=createReviewUI(options);record.itemIndex=0;record.flipped=false;render();};window.remount();
    await createAllowanceUI({api}).refresh();
    const rename=document.createElement('button');rename.textContent='Rename fixture';rename.onclick=()=>createRenameDialog().open({name:'Old title',kind:'study-sets',save:async name=>{window.fixture.renamed=name;}});document.body.append(rename);
    </script>'''

    async def check():
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True,executable_path=chromium_executable())
            try:
                page=await browser.new_page(viewport={'width':390,'height':844})
                async def local(route):
                    name=route.request.url.rsplit('/',1)[-1]
                    await route.fulfill(body=(static/name).read_text() if name.endswith('.js') else '<link rel="stylesheet" href="/static/style.css">'+harness if name!='style.css' else (static/name).read_text(),content_type='text/javascript' if name.endswith('.js') else 'text/css' if name=='style.css' else 'text/html')
                await page.route('**/*',local);await page.goto('http://learning.local/')
                await page.wait_for_function("window.fixture.rounds.length===1 && document.querySelector('.review-status').hidden")
                assert not await page.get_by_role('button',name='✓ Correct',exact=True).is_visible()
                assert '75% left' in await page.locator('.allowance-header').inner_text()
                assert '25% used' in await page.locator('.allowance-header [role=progressbar]').get_attribute('aria-valuetext')
                assert 'Resets in 1h 00m' in await page.locator('.allowance-header').get_attribute('title')
                assert await page.locator('.allowance-header [role=progressbar]').get_attribute('aria-valuenow')=='75'
                await page.get_by_role('button',name='Flip',exact=True).click()
                await page.get_by_role('button',name='✓ Correct',exact=True).click()
                await page.wait_for_function("window.fixture.record.itemIndex===1 && document.querySelector('.review-status').hidden")
                await page.evaluate('window.remount()')
                await page.wait_for_function("window.fixture.record.itemIndex===1 && document.querySelector('.review-status').hidden")
                assert await page.evaluate('window.fixture.record.itemIndex')==1
                await page.evaluate('window.fixture.fail=true')
                await page.get_by_role('button',name='Flip',exact=True).click()
                await page.get_by_role('button',name='✕ Incorrect',exact=True).click()
                await page.get_by_role('button',name='Retry saving answer').click()
                await page.get_by_role('heading',name='50% correct').wait_for()
                assert '1 correct · 1 incorrect · 2 cards' in await page.locator('.review-summary').inner_text()
                assert await page.evaluate('window.fixture.rounds[0].answers.length')==2
                assert await page.evaluate("Object.keys(localStorage).filter(k=>k.includes('review-pending')).length")==0
                await page.get_by_role('button',name='Practice again').click()
                await page.get_by_role('button',name='Flip',exact=True).wait_for()
                assert await page.evaluate('window.fixture.rounds.length')==2
                await page.evaluate('window.fixture.conflict=true')
                await page.get_by_role('button',name='Flip',exact=True).click()
                await page.get_by_role('button',name='✓ Correct',exact=True).click()
                await page.get_by_role('button',name='Use saved progress').click()
                await page.wait_for_function("window.fixture.record.itemIndex===1 && document.querySelector('.review-status').hidden")
                assert await page.evaluate('window.fixture.record.itemIndex')==1
                await page.get_by_role('button',name='Rename fixture').click()
                await page.get_by_label('Name',exact=True).fill('My title')
                await page.get_by_role('button',name='Save name').click()
                await page.wait_for_function("window.fixture.renamed==='My title'")
                assert not await page.locator('dialog').is_visible()
                assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            finally:await browser.close()
    asyncio.run(check())
