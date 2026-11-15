import { SectionHead } from "../components/Actions";
import facts, { type CardRow, type FailedCheck } from "../site/facts";
import { cardValue, comparisonSymbol } from "../site/format";
import { LINKS } from "../site/links";

const passed = (row: CardRow) => row.status === "PASS";

function byGroup(rows: CardRow[]): [string, CardRow[]][] {
  const groups = new Map<string, CardRow[]>();
  for (const row of rows) groups.set(row.group, [...(groups.get(row.group) ?? []), row]);
  return [...groups.entries()];
}

/** Ring of passed (green) and failed (red) checks, with the count in the middle. */
function ScoreRing({ passedCount, failedCount, total }: { passedCount: number; failedCount: number; total: number }) {
  const length = 2 * Math.PI * 52; // circumference of the drawn ring, for the dash pattern
  const pass = (length * passedCount) / total;
  return (
    <div className="trust-score">
      <svg viewBox="0 0 120 120" role="img" aria-label={`${passedCount} of ${total} checks pass, ${failedCount} fails`}>
        <circle cx="60" cy="60" r="52" className="ring-bg" />
        <circle cx="60" cy="60" r="52" className="ring-pass" strokeDasharray={`${pass} ${length}`} />
        <circle cx="60" cy="60" r="52" className="ring-fail" strokeDasharray={`${(length * failedCount) / total} ${length}`} strokeDashoffset={-pass} />
      </svg>
      <div className="score-text"><strong>{passedCount}</strong><span>of {total} pass</span></div>
      <p className="muted small">{failedCount} fails and stays on the card.</p>
    </div>
  );
}

function FailedCheckCard({ check }: { check: FailedCheck }) {
  return (
    <article className="failed-row" aria-label={`Failed check ${check.id}`}>
      <div className="fr-badge">FAIL</div>
      <div className="fr-body">
        <h3>{check.quantity}</h3>
        <dl>
          <div><dt>Checked against</dt><dd>{check.compared_against}</dd></div>
          <div><dt>Cases</dt><dd>{check.cases}</dd></div>
          <div><dt>Required</dt><dd>{comparisonSymbol(check.threshold.comparison)} {cardValue(check.threshold, 0)}</dd></div>
          <div><dt>Measured</dt><dd className="fail-text">{cardValue(check.measured)}</dd></div>
        </dl>
        <p className="fr-limit">{check.limit}</p>
        <p className="source">Check <code>{check.id}</code> · {check.evidence}</p>
      </div>
    </article>
  );
}

/** The validation card: counts per group, every check as a dot, and each failed check in full. */
export function Trust() {
  const card = facts.card;
  return (
    <section className="section trust-sec" id="trust" aria-labelledby="trust-h">
      <div className="wrap">
        <SectionHead id="trust-h" eyebrow="Why the numbers can be trusted"
          title="For every comparison with an outside source, the pass criterion was committed first." />
        <div className="trust">
          <ScoreRing passedCount={card.passed} failedCount={card.failed} total={card.checks} />
          <div className="trust-groups">
            {byGroup(card.rows).map(([group, rows]) => (
              <div key={group} className="tg">
                <div className="tg-head"><span>{group}</span><span className="muted">{rows.filter(passed).length}/{rows.length}</span></div>
                <div className="tg-dots">
                  {rows.map((r) => <span key={r.id} className={`dot ${passed(r) ? "pass" : "fail"}`} title={`${r.status}: ${r.quantity}`} />)}
                </div>
              </div>
            ))}
          </div>
        </div>
        {card.failedRows.map((check) => <FailedCheckCard key={check.id} check={check} />)}
        <p className="source">
          From the validation card <a href={LINKS.card.href}>validation/card/validation_card.md</a>{" "}
          ({card.title.replace(/^Validation card:\s*/, "")}, {card.generated_utc}). The limits of every result are on{" "}
          <a href={LINKS.accuracy.href}>{LINKS.accuracy.label}</a>.
        </p>
      </div>
    </section>
  );
}
