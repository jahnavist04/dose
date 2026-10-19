# Dose 💊

**A medication safety net for families.**

About half of people on long-term medication don't take it as prescribed. Elders mix up pills, skip doses or run out, and family in another city finds out too late. Dose closes the loop: it builds a schedule from a prescription, reminds the patient, notices missed doses, and keeps the family informed.

> ⚠️ Dose is a reminder and safety-net tool. It is **not medical advice** and does not replace a doctor or pharmacist.

Built for the **Build, Ship, Shape: Amazon Developer Hackathon** (Alexa+ track, with the AWS Builder and Open Source mini challenges).

## What it does

1. **Prescription to schedule.** Read a handwritten prescription photo (for example `1-0-1` patterns) and turn it into a medicine schedule. The user confirms before anything is saved.
2. **Reminders.** Remind the patient by voice, log "taken", "later" or "skipped", and re-ask when there's no answer.
3. **Family alerts.** Alert family after missed doses.
4. **Safety checks.** Flag duplicate medicines (two brand names, one generic) and known interactions, using named sources, never a model's guess.
5. **Family dashboard.** Adherence, refills and alerts at a glance.
6. **Weekly summary.** One calm weekly message for the family.

## Status

| Feature | Status |
|---|---|
| MCP server (Streamable HTTP) | ✅ Done |
| Reminder and adherence logic | ✅ Done |
| Family dashboard | ✅ Done |
| Automated tests (reminders, adherence, dashboard, MCP) | ✅ Done |
| Prescription photo reading with Amazon Bedrock | 🔄 Tested in playground, code in progress |
| Duplicate and interaction checker | 🔄 In progress |
| Weekly family summary | ⏳ Planned |

## How it works

Dose is a self-hosted **MCP server** (Streamable HTTP) that Alexa+ connects to. **Amazon Bedrock** (Amazon Nova Lite) reads prescription photos.

```
Prescription photo --> Amazon Bedrock --> medicines + schedule
                                              |
Alexa+ <--> MCP server <--> reminders, dose log, adherence
                                              |
                              family alerts + dashboard
```

## Project structure

| Path | What it is |
|---|---|
| `server.py` | MCP server and tools |
| `reminders.py` | Reminder and adherence logic |
| `test_*.py` | Automated tests |
| `docs/BEDROCK_NOTES.md` | How Amazon Bedrock is used |
| `docs/PRODUCT_FEEDBACK.md` | Product feedback for hackathon judges |
| `docs/SAFETY.md` | Safety approach |
| `docs/WHAT_I_BUILT_DURING_THE_WINDOW.md` | What was built during the hackathon |
| `FRICTION_LOG.md` | Friction log of problems hit while building |
| `tests/samples/` | Fake sample prescriptions for testing |

## Run it

```bash
git clone https://github.com/jahnavist04/dose.git
cd dose
python -m venv .venv
# Windows: .venv\Scripts\activate    Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # then fill in your own values
python server.py
```

Run the tests:

```bash
pytest
```

## Configuration

Copy `.env.example` to `.env` and set your own values. Never commit `.env` or any AWS keys.

```
AWS_REGION=ap-southeast-2
BEDROCK_MODEL_ID=
```

## Safety

- Prescription photos are read by an AI model, so results are confirmed by the user before saving.
- The model is told to write "unclear" instead of guessing and never to add medicines that aren't written.
- Interaction warnings come only from named sources. Serious ones say "ask your pharmacist".
- All demo and test data is fake. No real patient data is stored.

See `docs/SAFETY.md`.

## Team

- **Jahnavi S T** ([@jahnavist04](https://github.com/jahnavist04)): AI and safety (Bedrock extraction, interaction checks, summaries)
- **Vomla P** ([@vomlap-25](https://github.com/vomlap-25)): Alexa+ integration, reminders, dashboard

## License

MIT, see [LICENSE](LICENSE).
