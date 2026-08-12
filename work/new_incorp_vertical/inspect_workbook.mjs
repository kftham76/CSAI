import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const sourcePath = "D:/CSAI_DATA/Database/New Incorp.xlsx";
const workDir = "C:/CSAI_OS/work/new_incorp_vertical";

const input = await FileBlob.load(sourcePath);
const workbook = await SpreadsheetFile.importXlsx(input);

const summary = await workbook.inspect({
  kind: "workbook,sheet,region,computedStyle",
  sheetId: "Sheet1",
  range: "A1:T10",
  maxChars: 10000,
  tableMaxRows: 12,
  tableMaxCols: 20,
  tableMaxCellChars: 160,
});
console.log(summary.ndjson);

await fs.mkdir(`${workDir}/before`, { recursive: true });
const sheets = workbook.worksheets.items;
for (const sheet of sheets) {
  const used = sheet.getUsedRange();
  console.log(JSON.stringify({
    sheet: sheet.name,
    usedAddress: used?.address ?? null,
    rowCount: used?.rowCount ?? null,
    columnCount: used?.columnCount ?? null,
  }));
  const tableInfo = sheet.tables.items.map((table) => ({
    name: table.name,
    style: table.style,
    showHeaders: table.showHeaders,
    showFilterButton: table.showFilterButton,
  }));
  console.log(JSON.stringify({ sheet: sheet.name, tables: tableInfo }));
  const preview = await workbook.render({
    sheetName: sheet.name,
    range: "A1:T10",
    scale: 1,
    format: "png",
  });
  const safeName = sheet.name.replace(/[<>:"/\\|?*]/g, "_");
  await fs.writeFile(`${workDir}/before/${safeName}.png`, new Uint8Array(await preview.arrayBuffer()));
}
