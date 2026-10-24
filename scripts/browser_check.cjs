/* Optional end-to-end checks: start formula-lab first, then npm run check:browser. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const base = process.env.FORMULA_LAB_URL || 'http://127.0.0.1:8765';
const out = path.resolve(process.env.FORMULA_LAB_ARTIFACTS || 'artifacts/browser');

(async () => {
  await fs.mkdir(out, {recursive:true});
  const browser = await chromium.launch({headless:true, executablePath:process.env.FORMULA_LAB_BROWSER || chromium.executablePath()});
  try {
    const page=await browser.newPage({viewport:{width:1512,height:1100},deviceScaleFactor:1});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base);
    await page.waitForFunction(()=>document.querySelector('#original-preview .math-token'));
    const request=page.request;
    const cases=[{page:4,contains:'𝑥∈',name:'membership'},
                 {page:4,contains:'ℚ',name:'fraction'},
                 {page:7,contains:'∑',name:'sum-product'},
                 {page:15,contains:'2𝑛+3',name:'multiline'}];
    const results=[];
    for (const example of cases) {
      const data=await (await request.get(`${base}/api/pages/${example.page}`)).json();
      const candidate=data.candidates.find(c=>c.text.includes(example.contains));
      assert(candidate, `Missing ${example.name} candidate`);
      const formula=await (await request.post(`${base}/api/preview`,{data:{page:example.page,bbox:candidate.bbox,title:example.name}})).json();
      assert.equal(formula.warnings.length,0);
      const facts=await page.evaluate(async formula=>{
        const old=document.getElementById('qa-formula'); if(old)old.remove();
        const root=document.createElement('div');root.id='qa-formula';
        Object.assign(root.style,{position:'fixed',left:'0',top:'0',background:'white',zIndex:'10000',minHeight:'0',overflow:'hidden'});
        document.body.append(root);await window.FormulaLab.render(root,formula,4);
        root.style.width=`${Math.ceil(formula.width*4)}px`;root.style.height=`${Math.ceil(formula.height*4)}px`;
        await document.fonts.ready;
        return {tokens:root.querySelectorAll('.math-token').length,
                rules:root.querySelectorAll('.math-rule').length,
                images:root.querySelectorAll('img,canvas,svg').length,
                loaded:formula.fonts.every(f=>!f.url||document.fonts.check(`12px "${f.id}"`))};
      },formula);
      assert.equal(facts.images,0);assert(facts.tokens>0);assert(facts.loaded);
      await page.locator('#qa-formula').screenshot({path:path.join(out,`${example.name}.png`)});
      await page.evaluate(()=>document.getElementById('qa-formula').remove());
      results.push({...example,bbox:candidate.bbox,width:formula.width,height:formula.height,...facts});
    }
    // Exercise the actual sign-edit controls and stored lineage.
    await page.locator('#page').fill('7');
    await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/pages/7')),page.locator('#page-form button').click()]);
    await page.locator('#candidate').selectOption({label: await page.locator('#candidate option').filter({hasText:'∑'}).textContent()});
    await page.waitForFunction(()=>document.querySelector('#original-preview')?.textContent.includes('+') && !document.getElementById('make-variant').disabled);
    const old=await page.locator('#original-preview').textContent();
    await page.locator('#make-variant').click();
    await page.waitForFunction(()=>!document.getElementById('variant-section').hidden);
    assert.equal(await page.locator('#original-preview').textContent(),old);
    assert((await page.locator('#variant-preview').textContent()).includes('−'));
    const records=await (await request.get(`${base}/api/formulas`)).json();
    const variant=records.findLast(r=>r.original_id);
    assert(variant && records.some(r=>r.id===variant.original_id));
    await page.screenshot({path:path.join(out,'workbench.png'),fullPage:true});
    await page.reload();
    await page.waitForFunction(()=>document.querySelector('#saved-list button'));
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false);
    assert.deepEqual(errors,[]);
    await fs.writeFile(path.join(out,'results.json'),JSON.stringify({cases:results,pageErrors:errors,variantId:variant.id},null,2));
    console.log(JSON.stringify({passed:true,cases:results,artifacts:out},null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
