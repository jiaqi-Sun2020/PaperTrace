/* Real Chromium regression. Run with NODE_PATH pointing at bundled Playwright. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const os = require('node:os');
const crypto = require('node:crypto');
const { chromium } = require('playwright');

async function main() {
  const reader = path.resolve(process.argv[2]);
  const reportPath = process.argv[3];
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'papertrace-feedback-'));
  let context;
  const rounds = [];
  try {
    context = await chromium.launchPersistentContext(profile, { channel: 'chrome', headless: true, viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
    await context.route(/^https?:/, route => route.abort());
    let page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const url = pathToFileURL(path.join(reader, 'reader_interactive.html')).href;
    await page.goto(url);
    const key = await page.evaluate(() => window.PaperTraceFeedbackRecovery.create().storageKey);
    const saved = () => page.evaluate(key => JSON.parse(localStorage.getItem(key)), key);
    const widths = () => page.evaluate(() => ({
      source: document.querySelector('.reader-sidebar').getBoundingClientRect().width,
      article: document.querySelector('.layout > main').getBoundingClientRect().width,
      overflow: document.documentElement.scrollWidth > innerWidth
    }));

    for (const width of [1280, 1440, 1920]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.evaluate(() => {
        if (document.body.classList.contains('source-pages-collapsed')) document.getElementById('toggleSourcePages').click();
        if (!document.body.classList.contains('toc-collapsed')) document.getElementById('toggleContents').click();
        document.getElementById('openFreeFeedback').click();
      });
      const before = await widths();
      const handle = page.locator('#sourcePaneResizer');
      await handle.focus();
      await page.keyboard.press('ArrowLeft');
      if ((await widths()).source >= before.source - 1) {
        await page.keyboard.press('ArrowRight');
        assert((await widths()).source > before.source + 1, 'keyboard source resize has no effect with feedback open: ' + JSON.stringify({ width, before, after: await widths(), details: await page.evaluate(() => ({ grid: getComputedStyle(document.querySelector('.layout')).gridTemplateColumns, source: document.querySelector('.layout').style.getPropertyValue('--source-pane-width'), body: document.body.className })) }));
      }
      const bounds = await handle.boundingBox();
      const dragBefore = await widths();
      await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + Math.min(bounds.height / 2, 100));
      await page.mouse.down();
      await page.mouse.move(bounds.x + bounds.width / 2 - 35, bounds.y + Math.min(bounds.height / 2, 100));
      await page.mouse.up();
      if ((await widths()).source === dragBefore.source) {
        // At the minimum, the opposite direction must remain usable.
        await handle.focus(); await page.keyboard.press('ArrowRight');
      }
      const open = await widths();
      assert(open.article >= (width >= 1680 ? 620 : 520) - 1, 'article minimum was lost');
      assert(!open.overflow, 'reader has horizontal overflow');
      await page.evaluate(() => document.getElementById('closeFeedback').click());
      assert(Math.abs((await widths()).source - open.source) < 1, 'closing feedback changed source width');
      await page.reload();
      assert(Math.abs((await widths()).source - open.source) < 1, 'reload lost source width');
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => document.getElementById('openFreeFeedback').click());
    assert(await page.evaluate(() => {
      const rect = document.getElementById('feedbackDock').getBoundingClientRect();
      return rect.bottom <= innerHeight && rect.top >= 0 && document.documentElement.scrollWidth <= innerWidth;
    }), 'mobile feedback is outside the viewport: ' + JSON.stringify(await page.evaluate(() => ({ body: document.body.className, rect: document.getElementById('feedbackDock').getBoundingClientRect().toJSON(), scrollWidth: document.documentElement.scrollWidth, width: innerWidth, hidden: document.getElementById('feedbackDock').hidden, overflow: [...document.querySelectorAll('body *')].filter(e => e.scrollWidth > e.clientWidth + 5 && getComputedStyle(e).overflowX === 'visible').slice(0,12).map(e => ({ tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width,scroll:e.scrollWidth,text:e.textContent.slice(0,60) })) }))));
    rounds.push({ round: 1, result: 'pass', evidence: '1280/1440/1920 keyboard, pointer, reload; 390 mobile drawer' });

    await page.setViewportSize({ width: 1440, height: 1000 });
    const identity = await page.evaluate(() => document.querySelector('.knowledge-gap[data-concept]').dataset.conceptId);
    assert(identity, 'fixture needs a real concept');
    for (const status of ['unknown', 'learning', 'unrated', 'known', 'mastered']) {
      await page.evaluate(status => {
        document.querySelector('.knowledge-gap[data-concept]').click();
        document.querySelector(`.status-buttons button[data-status="${status}"]`).click();
      }, status);
      assert.equal((await saved()).items.length, 1);
      await page.evaluate(() => document.getElementById('closeFeedback').click());
      await page.reload();
      for (const theme of ['default', 'sepia', 'dark', 'contrast']) {
        const result = await page.evaluate(({ identity, status, theme }) => {
          document.getElementById('readerThemeSelect').value = theme;
          document.getElementById('readerThemeSelect').dispatchEvent(new Event('change'));
          const marks = [...document.querySelectorAll('.knowledge-gap')].filter(m => m.dataset.conceptId === identity);
          const color = getComputedStyle(marks[0]).backgroundColor;
          return { consistent: marks.every(m => m.dataset.status === status && m.classList.contains(status)), color };
        }, { identity, status, theme });
        assert(result.consistent, 'recovered Original/Chinese concept statuses differ');
        assert.notEqual(result.color, 'rgba(0, 0, 0, 0)', 'recovered concept has no status background');
      }
      assert.equal(await page.locator('.saved-feedback-badge').count(), 1);
    }
    rounds.push({ round: 2, result: 'pass', evidence: 'five statuses, four themes, bilingual marks, reload, one badge' });
    await context.close();
    context = await chromium.launchPersistentContext(profile, { channel: 'chrome', headless: true, viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
    await context.route(/^https?:/, route => route.abort());
    page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(url);
    assert.equal((await saved()).items.length, 1, 'closing/restarting browser lost annotations');
    assert(await page.evaluate(() => document.querySelector('.knowledge-gap').classList.contains('mastered')));
    rounds[1].evidence += '; full browser close/restart with the same isolated profile';

    // Test the shared renderer in real DOM, independently of paper prose.
    const rangeResult = await page.evaluate(() => {
      const host = document.createElement('div');
      host.innerHTML = '<article>alpha <em>beta</em> gamma alpha beta gamma <code>secret</code> end</article>';
      document.body.appendChild(host);
      const scope = host.firstElementChild;
      const renderer = PaperTraceFeedbackUX.createAnnotationRenderer({ root: host, scopeForItem: () => scope });
      const range = document.createRange();
      range.setStart(scope.firstChild, 0); range.setEnd(scope.children[0].firstChild, 4);
      const locator = renderer.capture(range, scope);
      const a = { key: 'a', item: { selected_text: 'alpha beta', status: 'learning' }, locator };
      const b = { key: 'b', item: { selected_text: 'beta gamma alpha', status: 'unknown' } };
      const unresolved = renderer.render([a, b]);
      const firstCount = host.querySelectorAll('.saved-free-annotation').length;
      renderer.render([a, b]);
      const result = { located: unresolved.length === 0, countStable: firstCount === host.querySelectorAll('.saved-free-annotation').length,
        nested: !!host.querySelector('.saved-free-annotation .saved-free-annotation'),
        markup: scope.querySelector('em').textContent === 'beta', code: scope.querySelector('code').textContent === 'secret' };
      renderer.render([a]);
      result.remaining = !!host.querySelector('[data-feedback-key="a"]');
      result.ambiguous = renderer.render([{ key: 'old', item: { selected_text: 'alpha beta' } }]).length === 1;
      result.protected = renderer.render([{ key: 'math', item: { selected_text: 'gamma secret end' } }]).length === 1;
      host.remove();
      return result;
    });
    assert(rangeResult.located && rangeResult.countStable && !rangeResult.nested && rangeResult.markup && rangeResult.code
      && rangeResult.remaining && rangeResult.ambiguous && rangeResult.protected, JSON.stringify(rangeResult));
    rounds.push({ round: 3, result: 'pass', evidence: rangeResult });

    await page.locator('.bilingual-block .lang-panel.original p').first().scrollIntoViewIfNeeded();
    await page.evaluate(() => {
      const paragraph = document.querySelector('.bilingual-block .lang-panel.original p');
      const walker = document.createTreeWalker(paragraph, 4);
      let node;
      while ((node = walker.nextNode())) {
        if (node.nodeValue.trim().length > 12 && !node.parentElement.closest('.math-inline,.math-display,code')) break;
      }
      const range = document.createRange(); range.setStart(node, 0); range.setEnd(node, Math.min(24, node.nodeValue.length));
      window.scrollBy(0, range.getBoundingClientRect().top - 180);
      const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
    });
    await page.waitForTimeout(30);
    await page.locator('#readerSelectionToolbar [data-inline-status="learning"]').click();
    assert.equal((await saved()).items.length, 2);
    const freeKey = (await saved()).items.find(item => item.annotation_kind === 'freeform').feedback_id;
    assert((await saved()).locators[freeKey], 'range locator missing from internal recovery');
    assert(!(await page.locator('#feedbackExportFallback').inputValue()).includes('locators'), 'locator leaked into export');
    await page.reload();
    assert(await page.locator('.saved-free-annotation').count(), 'real saved selection did not restore');
    await page.locator('.saved-free-annotation').first().click();
    await page.evaluate(() => document.getElementById('deleteFeedback').click());
    assert.equal((await saved()).items.length, 1);
    await page.locator('#feedbackUndoStatus .papertrace-undo').click();
    assert.equal((await saved()).items.length, 2);
    assert(await page.locator('.saved-free-annotation').count(), 'undo lost range highlight');
    await page.locator('.saved-free-annotation').first().click();
    await page.evaluate(() => document.getElementById('deleteFeedback').click());

    await page.evaluate(() => {
      document.querySelector('.knowledge-gap[data-concept]').click();
      const note = document.getElementById('feedbackNote');
      note.value = 'Synthetic browser regression note'; note.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const download = page.waitForEvent('download');
    await page.evaluate(() => document.getElementById('downloadFeedback').click());
    await (await download).cancel();
    assert.equal((await saved()).items[0].note, 'Synthetic browser regression note');
    assert.equal((await saved()).items.length, 1);
    await page.evaluate(() => Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async () => {} } }));
    await page.evaluate(() => document.getElementById('copyFeedback').click());
    await page.waitForTimeout(30);
    assert.equal((await saved()).items.length, 1);
    await page.evaluate(() => Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async () => { throw new Error('test'); } } }));
    await page.evaluate(() => document.getElementById('copyFeedback').click());
    await page.waitForTimeout(30);
    assert.equal((await saved()).items.length, 1);
    assert(await page.locator('#feedbackExportFallback').inputValue());
    await page.evaluate(() => {
      window.confirm = () => true;
      window.__remove = Storage.prototype.removeItem;
      Storage.prototype.removeItem = () => { throw new Error('simulated deletion failure'); };
      document.getElementById('clearLocalFeedback').click();
    });
    assert.equal((await saved()).items.length, 1);
    assert.equal(await page.locator('.saved-feedback-badge').count(), 1);
    await page.evaluate(() => {
      Storage.prototype.removeItem = window.__remove;
      document.getElementById('clearLocalFeedback').click();
    });
    assert.equal(await saved(), null);
    assert.equal(await page.locator('.saved-feedback-badge').count(), 0);
    await page.waitForTimeout(350); await page.reload();
    assert.equal(await saved(), null);
    rounds.push({ round: 4, result: 'pass', evidence: 'download/copy/fallback retain data; failed clear retains UI; explicit clear stays cleared' });

    await page.evaluate(key => localStorage.setItem(key, '{invalid'), key);
    await page.reload();
    assert((await page.locator('#feedbackRecoveryStatus').textContent()).includes('invalid'));
    await page.evaluate(key => localStorage.removeItem(key), key);
    await page.evaluate(() => {
      Storage.prototype.setItem = () => { throw new Error('simulated quota'); };
      document.querySelector('.knowledge-gap[data-concept]').click();
      document.querySelector('.status-buttons button[data-status="learning"]').click();
    });
    assert((await page.locator('#feedbackRecoveryStatus').textContent()).includes('failed'));
    assert.equal(await page.locator('.saved-feedback-badge').count(), 1);
    assert.deepEqual(errors, [], 'page JavaScript errors');
    rounds.push({ round: 5, result: 'pass', evidence: 'invalid recovery rejected; quota failure visible; in-memory annotations and JSON export retained' });
    await context.close();
  } finally {
    if (context) await context.close();
    const resolved = fs.realpathSync(profile);
    assert.equal(path.dirname(resolved), fs.realpathSync(os.tmpdir()));
    assert(path.basename(resolved).startsWith('papertrace-feedback-'));
    fs.rmSync(resolved, { recursive: true, force: true });
  }
  const report = { status: 'pass', reader: path.basename(reader), browser: 'Chromium',
    html_sha256: crypto.createHash('sha256').update(fs.readFileSync(path.join(reader, 'reader_interactive.html'))).digest('hex'),
    checked_at: new Date().toISOString(), rounds };
  if (reportPath) fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
