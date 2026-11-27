import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs/promises";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { Workbook, SpreadsheetFile, FileBlob } = await import(require.resolve("@oai/artifact-tool"));

export async function writeCanvas(args) {
  const reader = fileURLToPath(new URL("./stage3_canvas.py", import.meta.url));
  const groups = JSON.parse(execFileSync("python3", [reader, args.input], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 }));
  const book = Workbook.create();
  const info = book.worksheets.add("提示词说明");
  info.getRange("A1:C1").values = [["场次", "镜头数", "时长（秒）"]];
  const records = [];
  for (const group of groups) {
    const {scene, globalPrompt, headers} = group;
    const sheet = book.worksheets.add("场次" + scene);
    const end = headers.length === 6 ? "F" : "E";
    const rows = group.rows.map(row => row.map((cell, index) =>
      index === 2 ? Number(cell.replace(/\s*(?:s|秒)$/i, "")) : cell.replace(/<br\s*\/?>/gi, "\n").replace(/\\\|/g, "|")));
    if (rows.some(row => !Number.isFinite(row[2]))) throw new Error("镜头时长无效");
    sheet.getRange("A1:" + end + "1").merge();
    sheet.getRange("A1").values = [["场次 " + scene + " 全局提示词"]];
    sheet.getRange("A1:" + end + "1").format = {fill:"#244459",font:{bold:true,color:"#FFFFFF"}};
    sheet.getRange("A2:" + end + "2").merge();
    const cell = globalPrompt.replace(/\\\|/g, "|");
    if (cell.length > 32767) throw new Error("场次 " + scene + " 超过 Excel 单元格长度上限");
    sheet.getRange("A2").values = [[cell]];
    sheet.getRange("A2:" + end + "2").format = {wrapText:true,verticalAlignment:"top",fill:"#EEF5F5",rowHeight:Math.min(405,24+18*cell.split("\n").reduce((n,line)=>n+Math.max(1,Math.ceil(line.length/85)),0))};
    sheet.getRange("A4:" + end + "4").values = [headers];
    sheet.getRange("A5:" + end + (4+rows.length)).values = rows;
    sheet.getRange("A4:" + end + "4").format = {fill:"#236875",font:{bold:true,color:"#FFFFFF"}};
    for (const [column,width] of [["A",12],["B",12],["C",12],["D",70],["E",100],["F",32]]) {
      sheet.getRange(column+":"+column).format.columnWidth=width;
    }
    const data=sheet.getRange("A5:"+end+(4+rows.length));
    data.format.wrapText=true;
    data.format.verticalAlignment="top";
    data.format.autofitRows();
    sheet.getRange("C5:C"+(4+rows.length)).format.numberFormat='0.0"秒"';
    records.push({scene,cell,rows,end});
  }
  info.getRange("A2:C"+(1+records.length)).values=records.map(({scene,rows})=>[scene,rows.length,rows.reduce((s,r)=>s+r[2],0)]);
  const output=path.resolve(args.output);
  await fs.mkdir(path.dirname(output),{recursive:true});
  const scratch = await fs.mkdtemp(path.join(path.dirname(output), ".canvas-export-"));
  const staged = path.join(scratch, "canvas.xlsx");
  try {
    await (await SpreadsheetFile.exportXlsx(book)).save(staged);
    const saved=await SpreadsheetFile.importXlsx(await FileBlob.load(staged));
    for (const {scene,cell,rows,end} of records) {
      const name="场次"+scene;
      const sheet=saved.worksheets.getItem(name);
      const actual=sheet.getRange("A5:"+end+(4+rows.length)).values;
      if(sheet.getRange("A2").values[0][0]!==cell || rows.some((r,i)=>r.some((v,j)=>(actual[i][j]??"")!==v))) throw new Error(name+" 导出回读不一致");
    }
    await fs.rename(staged, output);
  } finally {
    await fs.rm(scratch, {recursive: true, force: true});
  }
  console.log(JSON.stringify({output,scenes:groups.length,shots:records.reduce((s,r)=>s+r.rows.length,0)}));
}

const [input, output] = process.argv.slice(2);
if (!input || !output) throw new Error("用法：node export-canvas.mjs 主稿.md 画布.xlsx");
await writeCanvas({input, output});
