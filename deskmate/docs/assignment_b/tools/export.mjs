// 中文说明：从 Mermaid 和 Markdown 原稿重建 SVG、高清 PNG 与正式 PDF。
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';
import MarkdownIt from 'markdown-it';
import puppeteer from 'puppeteer';

const toolDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(toolDir, '..');
const build = path.join(root, '.build');
await fs.mkdir(build, { recursive: true });
const executablePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const chromeConfig = path.join(build, 'puppeteer.json');
await fs.writeFile(chromeConfig, JSON.stringify({ executablePath, args: ['--no-sandbox'] }));
const names = (await fs.readdir(path.join(root, 'figures'))).filter(n => n.endsWith('.mmd')).sort();
for (const name of names) {
  execFileSync(path.join(toolDir, 'node_modules/.bin/mmdc'), [
    '-i', path.join(root, 'figures', name), '-o', path.join(root, 'figures', name.replace('.mmd', '.svg')),
    '-p', chromeConfig, '-c', path.join(toolDir, 'mermaid.json'), '-b', 'white', '-w', '2000', '-H', '1800'
  ], { stdio: 'pipe' });
}
const browser = await puppeteer.launch({ executablePath, args: ['--no-sandbox'] });
try {
  const page = await browser.newPage();
  for (const name of names) {
    const svgPath = path.join(root, 'figures', name.replace('.mmd', '.svg'));
    const svg = await fs.readFile(svgPath, 'utf8');
    const box = svg.match(/viewBox="([^"]+)"/)[1].split(/[ ,]+/).map(Number);
    const width = 1800;
    const height = Math.ceil(box[3] / box[2] * width);
    await page.setViewport({ width, height, deviceScaleFactor: 1.5 });
    await page.setContent(`<html><head><style>body{margin:0;background:white}svg{width:100%;max-width:none!important;height:auto}</style></head><body>${svg}</body></html>`);
    await page.screenshot({ path: svgPath.replace('.svg', '.png'), fullPage: true });
    console.log(`${name} -> SVG and PNG`);
  }
  const md = new MarkdownIt({ html: false, linkify: true });
  md.renderer.rules.image = (tokens, index) => {
    const token = tokens[index];
    return `<figure><img src="${md.utils.escapeHtml(token.attrGet('src'))}"><figcaption>${md.utils.escapeHtml(token.content)}</figcaption></figure>`;
  };
  const source = await fs.readFile(path.join(root, 'SRS.md'), 'utf8');
  const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>DeskMate 桌伴软件需求规格说明书</title><style>
    @page{size:A4;margin:18mm 17mm 20mm}
    *{box-sizing:border-box}body{font-family:"PingFang SC","Noto Sans CJK SC",sans-serif;color:#111;font-size:10pt;line-height:1.65;margin:0}
    h1{font-size:24pt;line-height:1.4;margin:0 0 8mm;color:black}h2{font-size:16pt;margin:8mm 0 3mm;color:black;break-after:avoid}
    h3{font-size:12pt;margin:5mm 0 2mm;break-after:avoid}h4{font-size:10.8pt;margin:4mm 0 1.5mm;break-after:avoid}
    p{margin:0 0 3mm;orphans:3;widows:3;break-inside:avoid}li{margin-bottom:1.5mm}ul,ol{padding-left:6mm;margin:2mm 0 4mm}
    table{border-collapse:collapse;width:100%;font-size:9pt;margin:3mm 0 5mm;table-layout:auto}thead{display:table-header-group}
    th,td{border:0.5pt solid #d9d9d9;padding:2mm 2.4mm;text-align:left;vertical-align:middle;overflow-wrap:anywhere}
    th{background:#e6eef4;color:#000;font-weight:600}tr{break-inside:avoid}code{font-family:"SFMono-Regular",monospace;font-size:8.5pt;overflow-wrap:anywhere}
    figure{margin:5mm 0;break-inside:avoid;break-before:avoid;text-align:center}figure img{max-width:100%;max-height:165mm;width:auto;height:auto}figcaption{font-size:9pt;color:#333;margin-top:2mm}
    a{color:#1f4d67;text-decoration:none}strong{font-weight:600}
  </style></head><body><article>${md.render(source)}</article></body></html>`;
  const htmlPath = path.join(root, 'SRS.html');
  await fs.writeFile(htmlPath, html);
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'networkidle0' });
  await page.emulateMediaType('print');
  await page.pdf({ path: path.join(root, 'DeskMate_SRS_B.pdf'), preferCSSPageSize: true, printBackground: true,
    displayHeaderFooter: true, headerTemplate: '<div></div>', footerTemplate:
    '<div style="font-size:8px;width:100%;padding:0 17mm;color:#666;display:flex;justify-content:space-between"><span>DeskMate DM SRS 001 版本 1.0 草稿</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>' });
  console.log('SRS.html and DeskMate_SRS_B.pdf exported');
} finally { await browser.close(); }
