import { describe, expect, it } from "vitest";
import { draftAction, explain, scoreAppointment, segmentOf } from "./rules";
import type { TestVectors } from "./types";
import vectors from "./test-vectors.json";

const V = vectors as TestVectors;

describe("shared contract (data/test-vectors.json)", () => {
  it.each(V.vectors.map((v) => [v.label, v] as const))(
    "score: %s",
    (_label, v) => {
      const got = scoreAppointment(v.appointment);
      expect(got.score).toBe(v.expected.score);
      expect(got.segment).toBe(v.expected.segment);
      expect(got.prob).toBe(v.expected.prob);
      expect(got.features).toEqual(v.expected.features);
    },
  );

  it("segment boundaries", () => {
    expect(segmentOf(100)).toBe("CRITICAL");
    expect(segmentOf(85)).toBe("CRITICAL");
    expect(segmentOf(84)).toBe("ELEVATED");
    expect(segmentOf(55)).toBe("ELEVATED");
    expect(segmentOf(54)).toBe("LOW");
    expect(segmentOf(0)).toBe("LOW");
  });

  it("explain sorts highest weight first and skips tiny drivers", () => {
    const scored = scoreAppointment(V.vectors[0].appointment);
    const lines = explain(scored);
    expect(lines[0]).toContain("booking lead time x age");
    expect(lines[0]).toContain("+1.04 logit");
    expect(lines).toContain(
      "clinic catchment hotspot (Harbourfront): +0.35 logit",
    );
  });

  it("draft action mirrors the Python engine for every segment", () => {
    const appt = V.vectors[0].appointment;
    const crit = draftAction("CRITICAL", appt);
    expect(crit.channel).toBe("PHONE CALL");
    expect(crit.status).toBe("pending_human");
    expect(crit.title).toBe("Call V1 today");
    const elev = draftAction("ELEVATED", appt);
    expect(elev.channel).toBe("SMS");
    expect(elev.status).toBe("pending_human");
    const low = draftAction("LOW", appt);
    expect(low.channel).toBe("ROUTINE");
    expect(low.status).toBe("pending_human");
  });
});
