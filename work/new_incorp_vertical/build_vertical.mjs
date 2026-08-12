import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const sourcePath = "D:/CSAI_DATA/Database/New Incorp.xlsx";
const outputDir = "C:/CSAI_OS/outputs/019fef66-dfab-7ac0-9dd8-7a8a9bfb054b";
const outputPath = `${outputDir}/New Incorp - Vertical.xlsx`;
const previewDir = "C:/CSAI_OS/work/new_incorp_vertical/after";

const sourceBlob = await FileBlob.load(sourcePath);
const sourceWorkbook = await SpreadsheetFile.importXlsx(sourceBlob);
const sourceSheet = sourceWorkbook.worksheets.getItemAt(0);
const sourceValues = sourceSheet.getRange("A1:FC10").values;

// Preserve the reference-style vertical block in A:C, then transpose every
// remaining horizontal header/value pair from D:FC into additional rows.
const verticalRows = sourceValues.slice(0, 10).map((row) => [
  row[0] ?? null,
  row[1] ?? null,
  row[2] ?? null,
]);

for (let col = 3; col < 159; col += 1) {
  verticalRows.push([
    sourceValues[0]?.[col] ?? null,
    sourceValues[1]?.[col] ?? null,
    null,
  ]);
}

const workbook = Workbook.create();
const sheet = workbook.worksheets.add(sourceSheet.name || "Sheet1");
const lastRow = verticalRows.length;
const outputRange = sheet.getRange(`A1:C${lastRow}`);
outputRange.values = verticalRows;

// Match the simple Calibri/gridline presentation shown in the reference image.
sheet.showGridLines = true;
outputRange.format = {
  font: { name: "Calibri", fontSize: 11, color: "#000000" },
  verticalAlignment: "top",
};
sheet.getRange(`A1:A${lastRow}`).format = {
  font: { name: "Calibri", fontSize: 11, color: "#000000" },
  verticalAlignment: "top",
  wrapText: true,
  columnWidthPx: 315,
};
sheet.getRange(`B1:B${lastRow}`).format = {
  font: { name: "Calibri", fontSize: 11, color: "#000000" },
  verticalAlignment: "top",
  wrapText: true,
  columnWidthPx: 680,
};
sheet.getRange(`C1:C${lastRow}`).format = {
  font: { name: "Calibri", fontSize: 11, color: "#000000" },
  verticalAlignment: "top",
  horizontalAlignment: "right",
  columnWidthPx: 90,
};
sheet.getRange(`C1:C${lastRow}`).format.numberFormat = "0";

// Use an integer display for long identifiers so Excel shows every digit
// instead of switching numeric-looking text to scientific notation.
for (let rowIndex = 0; rowIndex < verticalRows.length; rowIndex += 1) {
  const label = String(verticalRows[rowIndex]?.[0] ?? "");
  if (/\bIC\b|ID No|Contact No|Reg No|Reference no\./i.test(label)) {
    sheet.getRange(`B${rowIndex + 1}`).format.numberFormat = "0";
  }
}
outputRange.format.autofitRows();

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);

// Re-import the exported file so verification covers the delivered artifact.
const checkBlob = await FileBlob.load(outputPath);
const checkWorkbook = await SpreadsheetFile.importXlsx(checkBlob);
for (const range of ["A1:C30", "A90:C110", `A154:C${lastRow}`]) {
  const keyCheck = await checkWorkbook.inspect({
    kind: "table",
    sheetId: sheet.name,
    range,
    maxChars: 6000,
    tableMaxRows: 30,
    tableMaxCols: 3,
    tableMaxCellChars: 180,
  });
  console.log(keyCheck.ndjson);
}

const errors = await checkWorkbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const previewRanges = ["A1:C55", "A56:C110", `A111:C${lastRow}`];
for (let i = 0; i < previewRanges.length; i += 1) {
  const preview = await checkWorkbook.render({
    sheetName: sheet.name,
    range: previewRanges[i],
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    `${previewDir}/Sheet1-${i + 1}.png`,
    new Uint8Array(await preview.arrayBuffer()),
  );
}

console.log(JSON.stringify({
  outputPath,
  sourceColumnsTransposed: 156,
  outputRows: lastRow,
  outputColumns: 3,
  sheet: sheet.name,
}));
