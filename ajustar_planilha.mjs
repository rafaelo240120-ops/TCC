import fs from "node:fs/promises";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const entrada = "base_ise_ibrx_selic.csv";
const saida = "base_ise_ibrx.xlsx";

const csvText = await fs.readFile(entrada, "utf8");
const linhas = csvText.trim().split(/\r?\n/);
const tabela = [["data", "ise_b3", "ibrx100", "selic_aa"]];

for (let i = 1; i < linhas.length; i++) {
  const partes = linhas[i].split(",");
  const data = partes[0];
  const ise = Number(partes[1]);
  const ibrx = Number(partes[2]);
  const selic = Number(partes[3]);
  tabela.push([data, ise, ibrx, selic]);
}

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("base_dados");
sheet.getRangeByIndexes(0, 0, tabela.length, 4).values = tabela;

sheet.freezePanes.freezeRows(1);

sheet.getRange("A1:D1").format.font.bold = true;
sheet.getRange("A1:D1").format.fill.color = "#D9EAF7";
sheet.getRange("A:A").setNumberFormat("@");
sheet.getRange("B:D").setNumberFormat("0.00");
sheet.getRange("A:D").format.autofitColumns();

const arquivo = await SpreadsheetFile.exportXlsx(workbook);
await arquivo.save(saida);

const conferida = await workbook.inspect({
  kind: "region",
  sheetId: "base_dados",
  range: "A1:D8",
  maxChars: 3000,
});

console.log(conferida.ndjson);
