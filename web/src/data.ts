import bookRaw from "./book.json";
import rescueRaw from "./rescue.json";
import summaryRaw from "./summary.json";
import type { AppointmentBook, RescueEntry, Summary } from "./types";

export const summary: Summary = summaryRaw as Summary;
export const book: AppointmentBook = bookRaw as AppointmentBook;
/** Engine rescue output, kept in the pipeline's rank order. */
export const rescueQueue: RescueEntry[] = rescueRaw as RescueEntry[];

export function fmtUSD(n: number): string {
  const body = Number.isInteger(n)
    ? n.toLocaleString("en-US")
    : n.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
  return `$${body}`;
}

export function fmtPct(n: number): string {
  return `${Number.isInteger(n) ? n.toString() : n.toFixed(1)}%`;
}
