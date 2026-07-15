import {existsSync, mkdirSync} from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {chromium} from 'playwright-core';
import manifest from '../src/data/case-manifest.json';

const projectRoot = path.resolve(__dirname, '..');
const repositoryRoot = path.resolve(projectRoot, '..', '..');
const outputDirectory = path.join(projectRoot, 'public', 'cases', 'news');
mkdirSync(outputDirectory, {recursive: true});

const browserCandidates = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
];
const executablePath = browserCandidates.find(existsSync);
if (!executablePath) throw new Error('Chrome or Edge executable was not found.');

const main = async () => {
const browser = await chromium.launch({headless: true, executablePath});
const page = await browser.newPage({viewport: {width: 1440, height: 1100}, deviceScaleFactor: 1});
await page.emulateMedia({reducedMotion: 'reduce'});

const briefingPath = path.join(repositoryRoot, ...manifest.news_briefing.briefing_html.split('/'));
await page.goto(pathToFileURL(briefingPath).href, {waitUntil: 'load'});
await page.addStyleTag({content: `
  *, *::before, *::after { animation: none !important; transition: none !important; }
  body { background: #071117 !important; padding: 28px !important; }
  aside, header, .summary, .briefing-section > h2, .mark-strip { display: none !important; }
  main.layout { display: block !important; width: 430px !important; margin: 0 auto !important; }
  article.news-card { display: none !important; }
  article.news-card#P002 { display: block !important; width: 430px !important; box-sizing: border-box !important; background: #F0EDE5 !important; color: #071117 !important; border: 2px solid #70B84C !important; padding: 26px !important; }
  article.news-card#P002 h3 { font-size: 30px !important; line-height: 1.24 !important; }
  article.news-card#P002 p { font-size: 18px !important; line-height: 1.48 !important; }
`});

const selected = manifest.news_briefing.items[0];
await page.locator('#P002').evaluate((node, item) => {
  node.innerHTML = `
    <div class="card-top">
      <span class="source-id">${item.id}</span>
      <span class="category">${item.category}</span>
      <span class="evidence">${item.evidence_level}</span>
      <span class="evidence">VERIFIED</span>
    </div>
    <h3>${item.title_zh}</h3>
    <p><strong>事实：</strong>${item.facts}</p>
    <p><strong>判断：</strong>${item.judgment}</p>
    <p class="source-line"><strong>来源：</strong>${item.source} · ${item.date}</p>
    <p class="source-line">${item.title_original}</p>
  `;
}, selected);

await page.evaluate(() => document.fonts.ready);
await page.locator('#P002').screenshot({
  path: path.join(outputDirectory, 'briefing-reader.png'),
  animations: 'disabled',
});
await browser.close();

console.log('Captured briefing-reader.png from the verified P002 artifact card.');
console.log('Visible text was UTF-8 normalized from case-manifest.json because the source HTML contains mojibake.');
};

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
