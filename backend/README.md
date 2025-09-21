# WhatsApp Collections MVP Backend

This directory contains a FastAPI backend that automates invoice delivery, reminder scheduling, promise-to-pay workflows, and bank reconciliation for WhatsApp-first SME collections.

## Getting started

1. **Install dependencies** (preferably in a virtual environment):

   ```bash
   cd backend
   pip install -e .[dev]
   ```

2. **Run the API server**:

   ```bash
   uvicorn app.main:app --reload
   ```

   The server exposes interactive API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

3. **Run the test suite**:

   ```bash
   pytest
   ```

## Data flows covered in the MVP

- **Invoice ingestion:** Upload CSV exports from Zoho/Tally/Vyapar to create invoices and automatically schedule smart reminders that respect business hours and key Indian holidays.
- **Promise-to-pay capture:** Snooze active reminders until the promised payment date and schedule a follow-up automatically.
- **Bank reconciliation:** Import bank statement CSVs, match payments to outstanding invoices with fuzzy amount/date checks, and mark invoices as paid.

## Next steps

- Plug in a WhatsApp Business API provider for actual message delivery.
- Extend the holiday calendar and reminder heuristics based on pilot feedback.
- Add user authentication and multi-tenant dashboards.
