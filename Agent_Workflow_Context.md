# Agentic AI Workflow — Full Context

## Overview

The AI agent automates insurance rating configuration by letting a user upload a single Excel file into the chat window. Gemini (via MCP) parses it, resolves missing context (company, LOB, state, product, entity), shows a structured preview card for review, and upon confirmation automatically creates:

**Rating Tables → Algorithm → Rating Plan → Rating Manual**

All four resource types are created in sequence with rollback safety if any step fails.

---

## Repositories

| Repo | Path | Branch |
|---|---|---|
| Backend API | `c:\Users\saile\OneDrive\Documents\GitHub\Ratings-api` | `feature/mcp-integration` |
| Frontend UI | `c:\Users\saile\OneDrive\Documents\GitHub\insurance_1\pnc-insurance-ui` | `ui-theme-fix` |

---

## End-to-End Flow

```
User attaches .xlsx in Chat UI
        │
        ▼
POST /api/v1/agent/upload-excel          ← FastAPI endpoint (agent.py)
        │   returns { bundle_id, table_summaries, parameters_detected, formula_detected }
        ▼
UI auto-sends chat message:
  "[bundle_id:<id>] I've uploaded <file.xlsx>. Please analyze it."
        │
        ▼
Gemini (gemini_mcp_client.py) receives message
  → runs 10-step Excel Import Workflow (SYSTEM_INSTRUCTION)
        │
        ├─ Step 1: detect [bundle_id:...] token
        ├─ Step 2: call analyze_excel_bundle(bundle_id) → gets raw headers + sample_rows
        ├─ Step 2b: classify each table semantically (type, variable_name, input/output cols, formula)
        ├─ Step 3: call apply_table_classifications(bundle_id, classifications, formula)
        ├─ Step 4: identify missing context fields
        ├─ Step 5: call resolve_reference_data(...) to fuzzy-match IDs
        ├─ Step 6: ask user for any still-missing fields
        ├─ Step 7: call preview_configuration(...) → returns <!--AGENT_REVIEW--> block
        │
        ▼
UI renders AgentReviewCard (structured preview)
  → User clicks "Confirm & Create"
  → UI sends "Confirmed. Please proceed..."
        │
        ▼
Gemini continues workflow:
        ├─ Step 8: create_rating_tables_from_bundle(...)    → returns table_ids[]
        ├─ Step 9: infer_algorithm(bundle_id, table_ids)    → builds calc steps from Gemini classifications
        ├─ Step 10: create_algorithm_from_bundle(...)       → returns algorithm_id
        ├─ Step 11: create_rating_plan_from_bundle(...)     → returns plan_id
        ├─ Step 12: create_rating_manual_from_bundle(...)   → returns manual_id
        │
        ▼
Gemini reports success with IDs of all created resources
(on any failure: rollback_session() deletes in reverse order)
```

---

## Backend

### Directory Structure (relevant files)

```
app/
├── api/v1/
│   ├── api.py                          # Router registration
│   └── endpoints/
│       ├── agent.py                    # /api/v1/agent/* endpoints
│       └── chat.py                     # /api/v1/chat/* endpoints (Gemini integration)
├── services/
│   ├── excel_parser.py                 # Excel parsing (multi-tab + single-tab)
│   └── agent_session.py                # File-based session persistence
└── mcp_server.py                       # All MCP tools (9 agent tools + existing tools)

gemini_mcp_client.py                    # Gemini client + SYSTEM_INSTRUCTION
```

---

### `app/services/excel_parser.py`

**Purpose:** Parse an Excel workbook into a `ParsedExcelBundle` containing rating tables, metadata parameters, and a resolved formula.

**Entry point:** `parse(file_bytes: bytes, sheet_name: Optional[str] = None) -> ParsedExcelBundle`

**Routing logic:**
- `sheet_name` given → single-sheet mode on that sheet
- `len(wb.sheetnames) > 1` → **multi-tab mode** (preferred)
- Otherwise → single-sheet mode on the active sheet

#### Multi-Tab Mode (preferred layout)

One sheet named `Config`, `Configuration`, `Metadata`, `Parameters`, `Algorithm`, or `Settings` → parsed as key/value pairs (parameters + formula). Every other sheet → one `TableSection`; the **sheet name becomes the section name and variable name**.

Config sheet example:
```
company          | ABC Insurance
lob              | Commercial Auto
state            | OH
effective_date   | 2025-01-01
algorithm_name   | BOP Premium Calc
formula          | BASE_RATE * STATE_FACTOR * PROGRAM_FACTOR * CREDIT_FACTOR
```

Table sheet example (`Age Factor` sheet):
```
Age Band | Factor
<25      | 1.30
25–65    | 1.00
>65      | 1.15
```

**Title row handling:** If the first non-blank row of a table sheet is a single non-numeric cell, it is treated as a display title and skipped — the sheet name is always used as the section/variable name.

#### Single-Tab Mode (fallback)

All tables stacked vertically, separated by blank rows. Parameters are key/value rows where the left cell is a known keyword. A formula cell is a single isolated cell containing `*`, `+`, `/`, or `lookup(`.

#### Table Classification (`_classify_table`)

| Type | Detection rule |
|---|---|
| `base_rate_table` | Any header contains "base_rate", "base rate", "base_premium" |
| `factor_table` | Exactly 1 numeric column + 1+ categorical columns |
| `decision_matrix` | Row labels match column headers (≥60% overlap) |
| `lookup_table` | Default fallback |

#### Variable Name Resolution (`_infer_variable_name`)

Variable names are used in the formula and in `build_calculation_steps`. Resolution priority:
1. If the **output column name** is already `UPPER_SNAKE_CASE` (e.g. `CREDIT_FACTOR`, `STATE_FACTOR`) → use it directly
2. Otherwise derive from section/sheet name via `_to_variable_name()` (strips filler words: table, factor, rate, lookup, rating; converts to UPPER_SNAKE_CASE)

This ensures the formula `BASE_RATE * STATE_FACTOR * CREDIT_FACTOR` matches the variable names even when sheet names differ from output column names (e.g. sheet `Credit_Score` with output column `CREDIT_FACTOR` → variable = `CREDIT_FACTOR`).

#### Formula Resolution (`_resolve_formula`)

| Priority | Source | Confidence |
|---|---|---|
| 1 | Explicit `formula` parameter row or isolated formula cell | 1.0 |
| 2 | Rules-based: `base_rate_table` found → `BASE_RATE * FACTOR1 * ...` | 0.85–0.95 |
| 2 | Rules-based: factor tables only → `FACTOR1 * FACTOR2 * ...` | 0.80 |
| 2 | Rules-based: decision matrices → `LOOKUP(TABLE1) + ...` | 0.75 |
| 3 | LLM fallback (empty string returned; Gemini asked to infer) | 0.0 |

#### Key Constants

```python
_CONFIG_SHEET_NAMES = {
    "config", "configuration", "metadata", "parameters", "algorithm", "settings"
}

_PARAM_KEYS = {
    "effective_date", "expiration_date", "algorithm_name", "algorithm name",
    "company", "lob", "state", "product", "entity", "priority",
    "formula", "table_type", "plan_name", "manual_name",
    "effective date", "expiration date", "plan name", "manual name",
}
```

#### `build_calculation_steps(tables, formula, table_ids)`

Called by the `infer_algorithm` MCP tool. Builds the `calculation_steps[]` and `variables{}` payload for `AlgorithmWorkflowBuilder`. Produces:
1. `data_intake` step with all unique input variable names
2. One `rating_table_lookup` step per table (linked by `table_id`)
3. `expression` step with the formula
4. `quote_output` step

---

### `app/services/agent_session.py`

**Purpose:** File-based persistence shared between the FastAPI process and the MCP subprocess (which runs as a child process and cannot share in-memory state).

**Storage directory:** `tempfile.gettempdir()/ratings_agent/` (e.g. `/tmp/ratings_agent/`)

| Function | File | Contents |
|---|---|---|
| `store_bundle(bundle_id, bundle_obj)` | `bundle_<id>.json` | Full `ParsedExcelBundle` serialized |
| `get_bundle(bundle_id)` | `bundle_<id>.json` | Returns dict or None |
| `store_inferred_algorithm(bundle_id, spec)` | `algorithm_<id>.json` | Algorithm spec from `infer_algorithm` |
| `get_inferred_algorithm(bundle_id)` | `algorithm_<id>.json` | Returns dict or None |
| `get_or_init_log(bundle_id)` | `log_<id>.json` | Creation log (tracks created IDs for rollback) |
| `save_log(bundle_id, log)` | `log_<id>.json` | Saves updated log |

**Log structure:**
```json
{
  "table_ids": [101, 102, 103, 104],
  "algorithm_id": 55,
  "plan_id": 33,
  "manual_id": 21
}
```

---

### `app/api/v1/endpoints/agent.py`

**Endpoints:**

#### `POST /api/v1/agent/upload-excel`

Accepts `.xlsx` or `.xls` multipart file upload.

**Form fields:**
- `file` (required) — the Excel file
- `session_id` (optional) — chat session ID for correlation

**Response:**
```json
{
  "bundle_id": "uuid-string",
  "session_id": "...",
  "table_summaries": [
    { "section_name": "BASE_RATE", "table_type": "base_rate_table", "column_count": 2, "row_count": 5 }
  ],
  "parameters_detected": { "company": "ABC Insurance", "lob": "Commercial Auto" },
  "formula_detected": "BASE_RATE * STATE_FACTOR * PROGRAM_FACTOR * CREDIT_FACTOR"
}
```

#### `GET /api/v1/agent/bundle/{bundle_id}`

Returns the full bundle summary (used for debugging / MCP tool inspection).

---

### `app/mcp_server.py` — Agent MCP Tools

Nine tools are registered (in addition to all pre-existing general-purpose tools). All make internal HTTP calls to `http://localhost:8000/api/v1/` using the existing `call_api()` helper. Auth passthrough works because `ENABLE_OIDC_SECURITY=false` in `.env`.

#### 1. `analyze_excel_bundle(bundle_id)`
Reads the stored bundle from disk. Returns:
- Table list (section_name, table_type, variable_name, row_count, input_columns, output_column)
- Parameters detected
- Formula detected / suggested formula / confidence
- Missing context fields (which of company_id, lob_id, state_id, product_id, entity_id are absent)

#### 2. `resolve_reference_data(company_name, lob_name, state_name, product_name, entity_name, effective_date)`
Fuzzy-matches provided names against live API data using `difflib.get_close_matches`. Calls:
- `GET /companies/` → matches company_name
- `GET /lobs/` → matches lob_name
- `GET /states/` → matches state_name
- `GET /products/` → matches product_name
- `GET /legal-entities/` → matches entity_name

Returns resolved IDs and match confidence for each field.

#### 3. `preview_configuration(bundle_id, company_id, lob_id, state_id, product_id, entity_id, ...)`
Builds a `<!--AGENT_REVIEW-->` JSON block for the UI to render as a Review Card. Does not create anything — read-only preview.

**Output format:**
```
<!--AGENT_REVIEW-->
{
  "bundle_id": "...",
  "company": "ABC Insurance",
  "lob": "Commercial Auto",
  "state": "OH",
  "product": "BOP",
  "entity": "...",
  "effective_date": "2025-01-01",
  "algorithm_name": "BOP Premium Calc",
  "formula": "BASE_RATE * STATE_FACTOR * PROGRAM_FACTOR * CREDIT_FACTOR",
  "plan_name": "...",
  "manual_name": "...",
  "tables": [
    { "section_name": "BASE_RATE", "table_type": "base_rate_table", "row_count": 5 }
  ]
}
<!--/AGENT_REVIEW-->
```

#### 4. `create_rating_tables_from_bundle(bundle_id, company_id, lob_id, state_id, product_id, entity_id, effective_date)`
POSTs to `POST /ratingtables/bulk_ratingtables`. Builds one rating table payload per `TableSection` in the bundle. Returns `{ table_ids: [101, 102, ...] }`. Saves IDs to the session log.

Response parsing: `result.get("results", [])` (bulk endpoint wraps in `{"results": [...], "total": N}`).

#### 5. `infer_algorithm(bundle_id, table_ids, algorithm_name, formula_override)`
Calls `build_calculation_steps(tables, formula, table_ids)` from `excel_parser`. Caches the algorithm spec via `agent_session.store_inferred_algorithm()`. Returns the full spec for inspection. Does **not** create anything in the DB.

#### 6. `create_algorithm_from_bundle(bundle_id, company_id, lob_id, state_id, product_id, entity_id, effective_date, algorithm_name)`
- Retrieves cached algorithm spec from `agent_session.get_inferred_algorithm()`
- If not cached, calls `infer_algorithm` first
- POSTs to `POST /algorithms/bulk_algorithms`
- Returns `{ algorithm_id: 55 }`. Saves to session log.

Response parsing: `result.get("items") or result.get("results") or []` (bulk endpoint returns raw list, wrapped by `call_api` as `{"items": [...], "count": N}`).

#### 7. `create_rating_plan_from_bundle(bundle_id, algorithm_id, company_id, lob_id, state_id, product_id, entity_id, plan_name, effective_date)`
POSTs to `POST /ratingplans/bulk_ratingplans`. Links the algorithm to the context dimensions. Returns `{ plan_id: 33 }`. Saves to session log.

#### 8. `create_rating_manual_from_bundle(bundle_id, table_ids, company_id, lob_id, state_id, product_id, entity_id, manual_name, priority, effective_date)`
POSTs to `POST /ratingmanuals/bulk_ratingmanuals`. Groups all imported rating tables under one manual. Returns `{ manual_id: 21 }`. Saves to session log.

#### 9. `rollback_session(bundle_id, rollback_to)`
Reads the session log and deletes created resources in **reverse order**:
1. DELETE manual
2. DELETE plan
3. DELETE algorithm
4. DELETE each table

`rollback_to` param controls how far to roll back: `"all"` | `"plan"` | `"algorithm"` | `"tables"`.

#### Naming Conflicts Avoided

Pre-existing general-purpose tools `create_algorithm`, `create_ratingplan`, `create_ratingmanual` take raw `Dict` payloads and are kept unchanged. Agent tools use the `_from_bundle` suffix to avoid FastMCP registration conflicts.

#### Helper Functions Added to `mcp_server.py`

```python
def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Coerce value to int; returns default if invalid."""
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default
```

Also added `Tuple` to the `from typing import ...` line.

---

### `gemini_mcp_client.py` — SYSTEM_INSTRUCTION

The 10-step Excel Import Workflow is embedded in `SYSTEM_INSTRUCTION`:

```
STEP 1  — Detect [bundle_id:<uuid>] token in user message
STEP 2  — Call analyze_excel_bundle(bundle_id)
STEP 3  — Identify missing context: company_id, lob_id, state_id, product_id, entity_id
STEP 4  — Call resolve_reference_data(...) to fuzzy-match user-provided names
STEP 5  — Ask user for any still-unresolved fields (one question, all at once)
STEP 6  — Call preview_configuration(...) → show <!--AGENT_REVIEW--> card, wait for confirmation
STEP 7  — On confirmation: call create_rating_tables_from_bundle(...), save table_ids
STEP 8  — Call create_algorithm_from_bundle(..., algorithm_id=<id>), save algorithm_id
STEP 9  — Call create_rating_plan_from_bundle(..., algorithm_id=<id>), save plan_id
STEP 10 — Call create_rating_manual_from_bundle(..., table_ids=<ids>), report success
         — On any failure: call rollback_session(bundle_id)
```

Available tool names listed in SYSTEM_INSTRUCTION (for Gemini's reference):
```
analyze_excel_bundle, resolve_reference_data, preview_configuration,
create_rating_tables_from_bundle, infer_algorithm, create_algorithm_from_bundle,
create_rating_plan_from_bundle, create_rating_manual_from_bundle, rollback_session
```

---

### Auth / Security Note

`ENABLE_OIDC_SECURITY=false` in `.env` means all internal HTTP calls from the MCP subprocess to the FastAPI server work without Bearer tokens. In production this would need to change.

---

### Bulk Endpoint Response Formats

Different bulk endpoints wrap their responses differently — this matters for the MCP tools:

| Endpoint | Wrapping by `call_api` | Parse with |
|---|---|---|
| `POST /ratingtables/bulk_ratingtables` | `{"results": [...], "total": N}` | `result.get("results", [])` |
| `POST /algorithms/bulk_algorithms` | `{"items": [...], "count": N}` | `result.get("items") or result.get("results") or []` |
| `POST /ratingplans/bulk_ratingplans` | `{"items": [...], "count": N}` | same |
| `POST /ratingmanuals/bulk_ratingmanuals` | `{"items": [...], "count": N}` | same |

`call_api()` wraps raw list responses from the backend as `{"items": [...], "count": N}`.

---

## Frontend (UI)

### Directory Structure (relevant files)

```
src/
├── lib/
│   └── api/
│       ├── apiClient.ts             # Generic HTTP client (postFormData reused for upload)
│       └── agentApi.ts              # NEW: agent-specific API calls
└── modules/
    └── chat-assistant/
        └── components/
            ├── ChatAssistant.tsx    # MODIFIED: file upload + bundle_id injection
            ├── ChatInput.tsx        # MODIFIED: attachment button + file chip
            ├── ChatMessage.tsx      # MODIFIED: renders AgentReviewCard
            └── AgentReviewCard.tsx  # NEW: review card component + parser
```

---

### `src/lib/api/agentApi.ts`

```typescript
export const agentApi = {
  uploadExcel: (file: File, sessionId?: string | null): Promise<ExcelUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (sessionId) formData.append('session_id', sessionId);
    return ApiClient.postFormData<ExcelUploadResponse>('/api/v1/agent/upload-excel', formData);
  },

  getBundle: (bundleId: string): Promise<BundleSummaryResponse> => {
    return ApiClient.get<BundleSummaryResponse>(`/api/v1/agent/bundle/${bundleId}`);
  },
};
```

Uses the pre-existing `ApiClient.postFormData` which sets `Content-Type: multipart/form-data` automatically.

---

### `ChatInput.tsx` Changes

**New props:**
```typescript
interface ChatInputProps {
  onSendMessage: (message: string) => void;
  onFileUpload?: (file: File) => void;   // NEW
  disabled?: boolean;
  isUploading?: boolean;                  // NEW
  placeholder?: string;
}
```

**New UI elements:**
- Hidden `<input type="file" accept=".xlsx,.xls" ref={fileInputRef} />`
- Paperclip button (`Paperclip` icon from lucide-react) — only rendered when `onFileUpload` is provided
- Pending file chip (dismissible) shown above the input bar when a file is selected
- Send button works for both text messages and pending file uploads
- Status bar shows "Uploading and parsing Excel file…" during `isUploading`

**Behavior:** When a file is selected, it is stored as `pendingFile` state. Clicking Send (or pressing Enter) calls `onFileUpload(pendingFile)` instead of `onSendMessage`.

---

### `ChatAssistant.tsx` Changes

**New state:**
```typescript
const [isUploading, setIsUploading] = useState(false);
```

**New handler:**
```typescript
const handleFileUpload = async (file: File) => {
  setIsUploading(true);
  // 1. Add "📎 filename.xlsx" as user message
  // 2. Call agentApi.uploadExcel(file, chatClient.getSessionId())
  // 3. Auto-send: "[bundle_id:<id>] I've uploaded <file.name>. It contains N rating table(s)..."
  // 4. On error: show error message in chat
  setIsUploading(false);
};
```

**Passes down to children:**
- `onFileUpload={handleFileUpload}` → `ChatInput`
- `isUploading={isUploading}` → `ChatInput`
- `onSendMessage={handleSendMessage}` → `ChatMessage` (for Review Card confirm/cancel)

---

### `AgentReviewCard.tsx` (New)

**`parseAgentReview(content: string)`**

Extracts the `<!--AGENT_REVIEW-->...<!--/AGENT_REVIEW-->` block from a message string. Returns `{ before, data, after }` or `null` if no block found.

**`AgentReviewCard` component**

Renders a structured preview card with:

| Section | Content |
|---|---|
| Header | "Rating Configuration Preview" with gradient icon |
| Context fields | Company, LOB, State, Product, Entity, Effective Date (with icons) |
| Rating Tables | List with type badge (Base Rate / Factor / Decision Matrix / Lookup) and row count |
| Formula | Code block with dark background |
| Names | Algorithm name, Plan name, Manual name |
| Action buttons | **Confirm & Create** (blue gradient) / **Cancel** (outline) |

**State management:** Buttons disable themselves after one click. Shows "Creation in progress…" or "Cancelled" feedback inline.

**Confirm action:** Calls `onConfirm("Confirmed. Please proceed with creating the rating tables, algorithm, rating plan, and rating manual as shown in the preview.")`

**Cancel action:** Calls `onCancel("Cancel. Please discard this configuration and start over.")`

---

### `ChatMessage.tsx` Changes

```typescript
// For every non-streaming assistant message:
const review = isAssistant && !isStreaming
  ? parseAgentReview(message.content ?? '')
  : null;

// If review found → render AgentReviewCard (with optional before/after text bubbles)
// If no review → render standard message bubble (unchanged)
```

`onSendMessage` prop is threaded through from `ChatAssistant` → `ChatMessage` → `AgentReviewCard` so confirm/cancel buttons can trigger chat messages.

---

## Excel File Format Reference

### Recommended Multi-Tab Layout

| Sheet name | Purpose |
|---|---|
| `Config` (or `Configuration`, `Metadata`, `Parameters`, `Algorithm`, `Settings`) | Key/value parameters + formula row |
| `Base Rate` | Base rate table (sheet name → `BASE_RATE` variable if output col not all-caps) |
| `Age Factor` | Factor table |
| `Territory Factor` | Factor table |
| *(any name)* | Any additional rating table |

### Config Sheet Supported Keys

```
company          lob              state            product
entity           effective_date   expiration_date  algorithm_name
algorithm name   plan_name        plan name        manual_name
manual name      formula          priority         table_type
```

### Variable Name Derivation

Variable names appear in the formula and link tables to algorithm lookup steps.

**Priority 1:** Output column name if already `UPPER_SNAKE_CASE` (e.g. `CREDIT_FACTOR` → `CREDIT_FACTOR`)

**Priority 2:** Sheet name processed by:
1. Strip filler words: `table`, `factor`, `rate`, `lookup`, `rating` (word-boundary match)
2. Replace non-alphanumeric with `_`
3. Strip leading/trailing `_`
4. `.upper()`

Examples: `Age Factor` → `AGE` (strips "factor"), `Program_Factor` → `PROGRAM_FACTOR` (underscore protects "factor" from word-boundary match), `State_Factor` → `STATE_FACTOR`

**Best practice:** Name output columns with the exact identifier you want in the formula (e.g. `CREDIT_FACTOR`, `STATE_FACTOR`, `BASE_RATE`). This avoids any ambiguity.

---

## Known Issues / Gotchas

1. **Session persistence across processes:** The MCP server runs as a subprocess. The only shared state is the file system (`/tmp/ratings_agent/`). Never use in-memory caches between `agent.py` endpoints and `mcp_server.py` tools.

2. **`call_api` list wrapping:** When a backend endpoint returns a raw list, `call_api` wraps it as `{"items": [...], "count": N}`. Always parse with `result.get("items") or result.get("results") or []` for algorithm/plan/manual bulk endpoints. Rating tables use `"results"` key directly.

3. **`_to_variable_name` strips "factor":** The word `factor` at a word boundary is stripped. `Age Factor` → `AGE`. Use output column names in all-caps to avoid this (see Variable Name Derivation above).

4. **Single-tab formula detection regex is narrow:** `_MATH_RE` only matches `*`, `+`, `/`, `lookup(`. Formulas using only `-`, `MIN()`, `MAX()`, `IF()` won't be auto-detected. Use a `formula` parameter row or the multi-tab Config sheet instead.

5. **`ENABLE_OIDC_SECURITY=false` required in dev:** The MCP subprocess makes unauthenticated HTTP calls to the FastAPI server. This works in dev but must be revisited for production.

6. **Pre-existing naming conflict avoided:** General-purpose MCP tools `create_algorithm`, `create_ratingplan`, `create_ratingmanual` (take raw `Dict` payloads) are kept. Agent tools use `_from_bundle` suffix: `create_algorithm_from_bundle`, `create_rating_plan_from_bundle`, `create_rating_manual_from_bundle`.

---

## Testing

### Test File

`app/Testing -AI Agent.xlsx` — 5-sheet workbook used to validate the parser:

| Sheet | Type | Variable | Rows |
|---|---|---|---|
| Configuration | Config | — | 6 params + formula |
| BASE_RATE | base_rate_table | `BASE_RATE` | 5 |
| Program_Factor | factor_table | `PROGRAM_FACTOR` | 5 |
| Credit_Score | factor_table | `CREDIT_FACTOR` | 5 |
| State_Factor | factor_table | `STATE_FACTOR` | 52 |

Formula in Config: `BASE_RATE * STATE_FACTOR * PROGRAM_FACTOR * CREDIT_FACTOR` (confidence 1.0, method: explicit)

### Parser Test Command

```bash
python -c "
import sys, json
sys.path.insert(0, '.')
from app.services.excel_parser import parse

with open('app/Testing -AI Agent.xlsx', 'rb') as f:
    data = f.read()

bundle = parse(data)
print('parameters:', json.dumps(bundle.parameters, indent=2))
print('formula:', bundle.formula_detected)
print('confidence:', bundle.formula_confidence)
for t in bundle.tables:
    print(f'  {t.section_name} → {t.table_type}, var={t.variable_name}, rows={t.row_count}')
"
```
