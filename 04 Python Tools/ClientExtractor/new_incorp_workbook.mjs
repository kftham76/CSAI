import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const [payloadPath, outputPath] = process.argv.slice(2);
if (!payloadPath || !outputPath) {
  throw new Error("Usage: node new_incorp_workbook.mjs payload.json output.xlsx");
}

const payload = JSON.parse(await fs.readFile(payloadPath, "utf8"));
if (!Array.isArray(payload.index) || !Array.isArray(payload.sheets)) {
  throw new Error("Workbook payload must contain index and sheets arrays");
}
if (payload.index.length !== 80 || payload.sheets.length !== 80) {
  throw new Error(`Expected 80 companies, received ${payload.sheets.length}`);
}

const workbook = Workbook.create();

const colors = {
  navy: "#17365D",
  blue: "#1F4E78",
  teal: "#0F6B78",
  paleBlue: "#D9EAF7",
  paleTeal: "#DDEBF7",
  paleGreen: "#E2F0D9",
  paleAmber: "#FFF2CC",
  white: "#FFFFFF",
  text: "#1F2937",
  border: "#B8C2CC",
};

function excelColumn(number) {
  let value = number;
  let label = "";
  while (value > 0) {
    value -= 1;
    label = String.fromCharCode(65 + (value % 26)) + label;
    value = Math.floor(value / 26);
  }
  return label;
}

function convertValue(row) {
  if (!row.value) return "";
  if (row.valueType === "date") {
    const match = String(row.value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (match) {
      return new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
    }
  }
  if (row.valueType === "datetime") {
    const match = String(row.value).match(
      /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/,
    );
    if (match) {
      return new Date(Date.UTC(
        Number(match[1]), Number(match[2]) - 1, Number(match[3]),
        Number(match[4]), Number(match[5]), Number(match[6]),
      ));
    }
  }
  return String(row.value);
}

function applyBaseStyle(sheet, lastRow) {
  const used = sheet.getRange(`A1:C${lastRow}`);
  used.format = {
    font: { name: "Aptos", fontSize: 10, color: colors.text },
    verticalAlignment: "top",
  };
  used.format.borders = {
    insideHorizontal: { style: "thin", color: colors.border },
    insideVertical: { style: "thin", color: colors.border },
    top: { style: "thin", color: colors.border },
    bottom: { style: "thin", color: colors.border },
    left: { style: "thin", color: colors.border },
    right: { style: "thin", color: colors.border },
  };
  sheet.getRange(`A1:A${lastRow}`).format.wrapText = true;
  sheet.getRange(`B1:C${lastRow}`).format.wrapText = true;
  sheet.getRange(`A1:A${lastRow}`).format.columnWidth = 39;
  sheet.getRange(`B1:B${lastRow}`).format.columnWidth = 76;
  sheet.getRange(`C1:C${lastRow}`).format.columnWidth = 24;
  used.format.autofitRows();
  sheet.showGridLines = false;
}


const indexSheet = workbook.worksheets.add("Index");
const indexHeaders = [
  "Sequence", "Worksheet", "Folder", "Company Name", "Reg No",
  "Section 14 Status", "Section 14 Source", "EBOS Status", "EBOS Source",
];
const indexValues = [
  indexHeaders,
  ...payload.index.map((item) => indexHeaders.map((header) => item[header] ?? "")),
];
indexSheet.getRange(`A1:I${indexValues.length}`).values = indexValues;
indexSheet.getRange("A1:I1").format = {
  fill: colors.navy,
  font: { name: "Aptos Display", bold: true, color: colors.white, fontSize: 11 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
indexSheet.getRange(`A2:I${indexValues.length}`).format = {
  font: { name: "Aptos", fontSize: 10, color: colors.text },
  verticalAlignment: "top",
  wrapText: true,
};
indexSheet.getRange(`A1:I${indexValues.length}`).format.borders = {
  insideHorizontal: { style: "thin", color: colors.border },
  insideVertical: { style: "thin", color: colors.border },
  top: { style: "thin", color: colors.border },
  bottom: { style: "thin", color: colors.border },
  left: { style: "thin", color: colors.border },
  right: { style: "thin", color: colors.border },
};
const widths = [10, 34, 45, 45, 27, 22, 65, 22, 65];
for (let index = 0; index < widths.length; index += 1) {
  const column = excelColumn(index + 1);
  indexSheet.getRange(`${column}1:${column}${indexValues.length}`).format.columnWidth = widths[index];
}
indexSheet.getRange(`A1:I${indexValues.length}`).format.autofitRows();
indexSheet.freezePanes.freezeRows(1);
indexSheet.showGridLines = false;
indexSheet.tables.add(`A1:I${indexValues.length}`, true, "NewIncorpIndex").style = "TableStyleMedium2";


for (const item of payload.sheets) {
  const sheet = workbook.worksheets.add(item.name);
  const rows = [[`New Incorporation Profile - ${item.title}`, "", ""], ["Field", "Value", "Auxiliary"]];
  const sectionRows = [];
  const dateRows = [];
  const datetimeRows = [];

  for (const section of item.sections) {
    sectionRows.push(rows.length + 1);
    rows.push([section.title, "", ""]);
    for (const row of section.rows) {
      const rowNumber = rows.length + 1;
      rows.push([row.field, convertValue(row), row.auxiliary ?? ""]);
      if (row.valueType === "date" && row.value) dateRows.push(rowNumber);
      if (row.valueType === "datetime" && row.value) datetimeRows.push(rowNumber);
    }
  }

  // Apply Text format before writing so Excel never coerces IC numbers,
  // phone numbers, MSIC codes, or certificate numbers to numeric/scientific
  // notation. Date objects receive explicit date formats below.
  sheet.getRange(`A1:C${rows.length}`).format.numberFormat = "@";
  sheet.getRange(`A1:C${rows.length}`).values = rows;
  sheet.getRange("A1:C1").merge();
  sheet.getRange("A1:C1").format = {
    fill: colors.navy,
    font: { name: "Aptos Display", bold: true, color: colors.white, fontSize: 14 },
    horizontalAlignment: "left",
    verticalAlignment: "center",
    rowHeight: 28,
  };
  sheet.getRange("A2:C2").format = {
    fill: colors.teal,
    font: { name: "Aptos", bold: true, color: colors.white, fontSize: 10 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  for (const rowNumber of sectionRows) {
    sheet.getRange(`A${rowNumber}:C${rowNumber}`).merge();
    sheet.getRange(`A${rowNumber}:C${rowNumber}`).format = {
      fill: colors.blue,
      font: { name: "Aptos Display", bold: true, color: colors.white, fontSize: 11 },
      verticalAlignment: "center",
      rowHeight: 23,
    };
  }
  applyBaseStyle(sheet, rows.length);
  sheet.getRange("A1:C1").format = {
    fill: colors.navy,
    font: { name: "Aptos Display", bold: true, color: colors.white, fontSize: 14 },
    horizontalAlignment: "left",
    verticalAlignment: "center",
    rowHeight: 28,
  };
  sheet.getRange("A2:C2").format = {
    fill: colors.teal,
    font: { name: "Aptos", bold: true, color: colors.white, fontSize: 10 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  for (const rowNumber of sectionRows) {
    sheet.getRange(`A${rowNumber}:C${rowNumber}`).format = {
      fill: colors.blue,
      font: { name: "Aptos Display", bold: true, color: colors.white, fontSize: 11 },
      verticalAlignment: "center",
      rowHeight: 23,
    };
  }
  for (const rowNumber of dateRows) {
    sheet.getRange(`B${rowNumber}`).format.numberFormat = "yyyy-mm-dd";
  }
  for (const rowNumber of datetimeRows) {
    sheet.getRange(`B${rowNumber}`).format.numberFormat = "yyyy-mm-dd hh:mm:ss";
  }
  sheet.getRange(`A3:A${rows.length}`).format.font = { name: "Aptos", bold: true, color: colors.text, fontSize: 10 };
  sheet.freezePanes.freezeRows(2);
}


const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);
console.log(`Workbook written: ${outputPath}`);
