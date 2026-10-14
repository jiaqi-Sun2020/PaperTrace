/* Offline Chromium behavior checks; all browser state is isolated. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');

function contrast(fg,bg){
  const lum = s => {const c=s.match(/[\d.]+/g).slice(0,3).map(v=>Number(v)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return .2126*c[0]+.7152*c[1]+.0722*c[2];};
  const a=lum(fg),b=lum(bg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
}

async function main(){
  const reader=path.resolve(process.argv[2]);
  const file=path.join(reader,'reader_interactive.html');
  const url=pathToFileURL(file).href;
  const browser=await chromium.launch({channel:'chrome',headless:true});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.route(/^https?:/,r=>r.abort());
  const page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const checks=[];
  try{
    await page.goto(url);
    assert.equal(await page.locator('#readerDocument > section').first().getAttribute('id'),'paper-history');
    assert.equal(await page.locator('.history-detail').count(),5);
    assert.equal(await page.locator('.history-detail[open]').count(),0);
    assert.equal(await page.locator('.bilingual-block').count(),121);
    assert.equal(await page.locator('.bilingual-block .reader-notes h3').count(),121);
    assert.equal(await page.locator('.history-node[aria-current="true"]').count(),1);
    assert.equal(await page.locator('.history-rail,.history-details').count(),0);
    assert.equal(await page.locator('.argument-map>li').count(),6);
    assert.equal(await page.locator('.logic-diagram').count(),159);
    for(const node of await page.locator('.history-contribution').all())assert(await node.isVisible());
    const embedded=JSON.parse(await page.locator('#paper-history-data').textContent());
    const disk=JSON.parse(fs.readFileSync(path.join(reader,'reader_wiki/paper_history.json'),'utf8'));
    assert.deepEqual(embedded,disk);
    checks.push({check:'content_order_and_full_coverage',result:'pass',evidence:'history first; five papers; 121 visible-source bilingual analysis blocks; embedded history equals file'});

    const first=page.locator('.history-detail summary').first();await first.focus();await page.keyboard.press('Enter');
    const target=await first.evaluate(el=>el.parentElement.id);
    assert.equal(await page.locator('#'+target).getAttribute('open'),'');
    assert.equal(await page.evaluate(()=>document.activeElement.tagName),'SUMMARY');
    await page.locator('#'+target+' summary').click();assert.equal(await page.locator('#'+target).getAttribute('open'),null);
    checks.push({check:'keyboard_and_native_details',result:'pass',evidence:'Enter opens matching details, focuses summary; native summary closes it'});

    const measured=[];
    for(const theme of ['default','sepia','dark','contrast']){
      await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
      for(const selector of ['#paper-history','.logic-node','.logic-connector']){
        const colors=await page.locator(selector).first().evaluate(el=>{
          let bg=getComputedStyle(el).backgroundColor,p=el;
          while((bg==='rgba(0, 0, 0, 0)'||bg==='transparent')&&p.parentElement){p=p.parentElement;bg=getComputedStyle(p).backgroundColor;}
          return {fg:getComputedStyle(el).color,bg};
        });
        const ratio=contrast(colors.fg,colors.bg);assert(ratio>=4.5,theme+' '+selector+' contrast '+ratio);measured.push({theme,selector,ratio});
      }
    }
    for(const width of [390,768,1280,1440,1920]){
      await page.setViewportSize({width,height:900});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'overflow at '+width);
      const geometry=await page.locator('#S009').evaluate(el=>({
        available:document.querySelector('#readerDocument').clientWidth,
        notes:el.querySelector('.reader-notes').getBoundingClientRect().width,
        pair:el.querySelector('.pair-grid').getBoundingClientRect().width,
        top:el.querySelector('.reader-notes').getBoundingClientRect().top,
        translatedBottom:el.querySelector('.translation').getBoundingClientRect().bottom,
      }));
      if(geometry.available<=1000){assert(geometry.notes>=geometry.pair-2);assert(geometry.top>=geometry.translatedBottom-2);}
    }
    checks.push({check:'themes_and_responsive',result:'pass',contrasts:measured,evidence:'no overflow at five widths; diagram text readable in four themes; analysis responds to actual article width'});

    await page.evaluate(()=>document.dispatchEvent(new Event('beforeprint')));
    assert.equal(await page.locator('.paper-history details[open]').count(),6);
    await page.evaluate(()=>document.dispatchEvent(new Event('afterprint')));
    assert.equal(await page.locator('.paper-history details[open]').count(),0);
    const plain=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
    await plain.route(/^https?:/,r=>r.abort());const nojs=await plain.newPage();await nojs.goto(url);
    await nojs.locator('.history-detail summary').first().click();assert(await nojs.locator('.history-detail-content').first().isVisible());
    await nojs.emulateMedia({media:'print'});
    const printBoxes=await nojs.locator('.history-detail-content').evaluateAll(els=>els.map(e=>e.getBoundingClientRect().height));
    assert(printBoxes.every(h=>h>0),'closed details lost in no-script print');
    await plain.close();
    checks.push({check:'offline_no_script_print',result:'pass',evidence:'native details opens without JS; print includes all closed paper details; scripted print restores prior folds'});
    assert.deepEqual(errors,[]);
    await page.setViewportSize({width:1440,height:1000});await page.evaluate(()=>document.documentElement.dataset.theme='default');await page.goto(url);
    if(process.argv[4])await page.screenshot({path:process.argv[4],fullPage:false});
  }finally{await context.close();await browser.close();}
  const report={status:'pass',browser:'Chromium',html_sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'),checked_at:new Date().toISOString(),checks,limitation:'Headless Chromium, not independent learner comprehension or real iOS Safari testing.'};
  if(process.argv[3])fs.writeFileSync(process.argv[3],JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
