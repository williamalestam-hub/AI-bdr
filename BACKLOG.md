# Backlog

Cherry-pick any of these next. Ordered roughly by impact-per-effort for the current (pre-keys, supervised Phase 1) stage.

1. **Reply classifier** — when a lead replies, classify interested / not-interested / wrong-person / unsubscribe. Branch the sequence accordingly (stop on not-interested, escalate on interested, remove from ALL outreach on unsubscribe).
2. **Compliance footer** — auto-append GDPR/CAN-SPAM unsubscribe line + sender address to every email. Mandatory before real sends.
3. **Dedupe & throttle** — same firm not contacted more than once per 14 days; same person not twice in 24 h. Should also catch the case where two BDRs hit the same firm.
4. **Cost + token tracking** — per-run Anthropic token usage and estimated spend logged alongside each `runs/digest-*.json`. Useful for budget gate.
5. **Prompt A/B variants** — two versions of the email prompt, random split across leads, track approval rate per variant. Plug into existing `write_email()` via a `variant` param.
6. **Reject-feedback loop** — when a rep rejects a draft in Slack, capture the reason text; surface top rejection patterns weekly to guide prompt edits.
7. **Multi-lingual** — FR / DE / ES variants for EU leads. Trigger by country from the enriched lead.
8. **Calendar integration** — replace `[CALENDLY_LINK]` with real booking slots via Cal.com or Calendly API.
9. **LLM-as-judge grading** — upgrade `scripts/grade.py` with a Claude-judge pass that scores tone/warmth on a 1–5 scale. Skeleton already noted in grade.py header.
10. **Observability** — structured JSON logs per agent, per-agent timing, OpenTelemetry traces.
11. **Reply handling via email thread** — parse inbound replies from Gmail MCP, link back to the original lead, trigger classifier + HubSpot log.
12. **Rep-in-the-loop editor** — Slack modal to edit a draft inline rather than kicking back for a re-draft.
13. **Per-lead kill switch** — `bdr_opt_out: true` on the contact record globally skips that contact, respected by every agent.
14. **Warm handoff to AE** — for SMB+ approved leads, create a HubSpot task on the assigned AE instead of sending directly.
15. **Per-firm batching** — rather than one lead at a time per firm, group by firm and give the rep a single decision per firm.
