<!--
Analyst.Jr — detailed architecture and workflow guide.
This document describes the implementation currently present in this repository.
See the safety notes for distinctions between intended behaviour and safeguards that still need strengthening.
-->

<div align="center">

# Analyst.Jr — Architecture & Workflow

**A personal junior data analyst powered by agentic AI**

Natural-language questions → intelligent routing → SQL analysis or ETL execution → structured results.

</div>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="Orchestration" src="https://img.shields.io/badge/Orchestration-LangGraph-2563EB?style=flat-square">
  <img alt="LLM" src="https://img.shields.io/badge/LLM-LangChain-1C3C3C?style=flat-square">
  <img alt="Data" src="https://img.shields.io/badge/Data-Pandas%20%7C%20PostgreSQL-150458?style=flat-square">
  <img alt="Validation" src="https://img.shields.io/badge/Validation-Pydantic-E92063?style=flat-square">
</p>

> **Purpose:** explain how Analyst.Jr works from input to output, including its router graph, SQL analyst graph, ETL analyst graph, model selection, database utilities, data flow, and important safety limitations. This is an implementation-focused guide, not just a feature list.

---

## Contents

1. [Project overview](#1-project-overview)
2. [High-level architecture](#2-high-level-architecture)
3. [Repository map](#3-repository-map)
4. [Technology stack](#4-technology-stack)
5. [How LangGraph state works here](#5-how-langgraph-state-works-here)
6. [Main agent: routing workflow](#6-main-agent-routing-workflow)
7. [SQL analyst workflow](#7-sql-analyst-workflow)
8. [ETL analyst workflow](#8-etl-analyst-workflow)
9. [ETL internals: extract, transform, load](#9-etl-internals-extract-transform-load)
10. [PostgreSQL setup and data model](#10-postgresql-setup-and-data-model)
11. [Dynamic LLM selection](#11-dynamic-llm-selection)
12. [End-to-end examples](#12-end-to-end-examples)
13. [Security, correctness, and engineering trade-offs](#13-security-correctness-and-engineering-trade-offs)
14. [Configuration and running the project](#14-configuration-and-running-the-project)
15. [Interview walkthroughs and questions](#15-interview-walkthroughs-and-questions)
16. [Glossary and revision checklist](#16-glossary-and-revision-checklist)

---

## 1. Project overview

Analyst.Jr is a Python-based agentic data-analysis project. A user can ask a question in natural language instead of manually writing SQL or a data-processing script.

The main graph classifies the request into one of two broad categories:

- **SQL analysis:** questions about data already stored in PostgreSQL, such as “Which payment methods are most common?” or “Show the top five users by ride count.”
- **ETL work:** requests to extract data from an API or transform a file and save the result in a requested format.

The main agent is a router, not the component that performs every operation itself. It delegates SQL questions to the SQL analyst graph and ETL questions to the ETL analyst graph.

~~~mermaid
flowchart TD
    U["Natural-language request"] --> R["Data Agent / Router"]
    R -->|SQL| S["SQL Analyst"]
    R -->|ETL| E["ETL Analyst"]
    S --> DB[("PostgreSQL")]
    E --> API["External API"]
    E --> FILES["Local CSV / JSON / Parquet files"]
    S --> A["User-friendly answer"]
    E --> B["Operation result / status"]
~~~

### What makes it agentic?

The workflow uses LLMs to classify intent, formulate SQL, decide which ETL tool to invoke, and generate a transformation program. LangGraph connects the operations into explicit node-and-edge workflows. Tool execution and database/file interactions are implemented by Python functions.

**Key distinction:** the model proposes a route, query, or operation; Python functions and the database execute the actual operation.

---

## 2. High-level architecture

~~~mermaid
flowchart TB
    Input["main.py<br/>HumanMessage"] --> RouterGraph["Data Agent graph<br/>agents/data_agent.py"]
    RouterGraph --> Router["router_node<br/>Structured RouterSchema output"]
    Router -->|answer = sql| SQLGraph["SQL Analyst graph"]
    Router -->|answer = etl| ETLGraph["ETL Analyst graph"]

    subgraph SQL["SQL analysis pipeline"]
      SQLGraph --> Curate["curate_ques"]
      Curate --> Context["prompt_query_context"]
      Context --> Generate["generate_sql"]
      Generate --> Judge["is_safe_sql"]
      Judge -->|Yes| Execute["execute_sql"]
      Judge -->|No| Cancel["canceled_sql"]
      Execute --> Format["represent_final_answer"]
    end

    subgraph ETL["ETL analysis pipeline"]
      ETLGraph --> LLM["LLM node with bound tools"]
      LLM -->|tool call| ToolNode["tool_node"]
      ToolNode --> Extract["extract_load_tool"]
      ToolNode --> Transform["transform_load_tool"]
      Extract --> Result["ToolMessage result"]
      Transform --> Result
      Result --> LLM
      LLM -->|no tool calls| Done["End"]
    end

    Execute --> Output["Response"]
    Cancel --> Output
    Format --> Output
    Done --> Output
~~~

### Main responsibilities

| Component | Responsibility |
|---|---|
| `main.py` | Example entry point; creates a `HumanMessage`, invokes the data-agent graph, and prints the result |
| `agents/data_agent.py` | Main router graph and sub-agent dispatch |
| `agents/sql_analyst.py` | SQL curation, schema context, query generation, safety judgment, execution, and answer generation |
| `agents/etl_analyst.py` | ETL tool definitions, tool selection loop, transformation-code generation, and execution calls |
| `utils/database.py` | PostgreSQL connection, schema inspection, and query execution |
| `utils/etl_tools.py` | HTTP extraction, JSON normalization, file loading, file context, and generated-code execution |
| `utils/llm_pick.py` | Chooses the configured model integration by requested level |
| `Models/schema.py` | Pydantic state and structured-output schemas |
| `feed_db.py` | Creates the sample PostgreSQL schema and loads CSV datasets |
| `data/` | Local sample datasets plus extraction/transformation output folders |

---

## 3. Repository map

~~~text
Analyst.Jr/
├── main.py                        # Example invocation of the main data agent
├── agents/
│   ├── data_agent.py               # Router graph: SQL vs ETL
│   ├── sql_analyst.py              # SQL-analysis graph
│   └── etl_analyst.py              # ETL graph and ETL tool wrappers
├── Models/
│   └── schema.py                   # Pydantic state / structured output schemas
├── utils/
│   ├── database.py                 # PostgreSQL utility
│   ├── etl_tools.py                # API/file operations and exec()
│   └── llm_pick.py                 # LLM provider/model selection
├── data/
│   ├── users.csv
│   ├── vehicles.csv
│   ├── rides.csv
│   ├── payments.csv
│   ├── ratings.csv
│   ├── extract/                    # Extracted output directory
│   └── transform/                 # Transformed output directory
├── feed_db.py                      # PostgreSQL DDL and CSV ingestion
├── test_schema_details.txt         # Generated schema context / inspection output
├── .env.example                    # Example environment configuration
├── pyproject.toml                  # Python project metadata / dependencies
├── requirements.txt                # Pinned package list
└── README.md                       # Project overview and usage
~~~

The code includes scripts that render LangGraph diagrams to PNG files when run directly. Those diagrams are development/debugging artefacts rather than requirements of the runtime workflow.

### Start with these files when reading the code

| Goal | File |
|---|---|
| Understand the execution entry point | `main.py` |
| Understand classification and branching | `agents/data_agent.py` |
| Follow SQL generation and validation | `agents/sql_analyst.py` |
| Follow API extraction and transformation tools | `agents/etl_analyst.py`, `utils/etl_tools.py` |
| Understand database schema context and execution | `utils/database.py` |
| Understand model configuration | `utils/llm_pick.py` |
| Understand graph state fields | `Models/schema.py` |
| Understand sample relational schema and CSV loading | `feed_db.py` |

---

## 4. Technology stack

| Technology | Role in this project |
|---|---|
| Python 3.12+ | Application language; required by `pyproject.toml` |
| LangGraph | Defines the main router, SQL analyst, and ETL analyst graphs |
| LangChain | Model integrations, chat messages, structured output, and tool calling |
| OpenAI-compatible API integration | `ChatOpenAI` instances created by the model-selection helper |
| Anthropic integration | `ChatAnthropic` used for the `claude` selection |
| Pydantic | Typed state structures and structured router / SQL-judge outputs |
| PostgreSQL | Relational database used for SQL questions |
| psycopg2 | Python driver for PostgreSQL |
| Pandas | Normalizes extracted JSON and reads/writes structured data files |
| Requests | Makes HTTP requests to external data APIs |
| python-dotenv / dotenv | Loads environment variables from the local `.env` file |
| PyArrow | Supports Parquet-related Pandas IO |
| CSV | Seed and sample datasets used for database ingestion and ETL workflows |

### Important terminology

- **Graph:** a workflow composed of nodes and edges.
- **Node:** a Python function responsible for one step of that workflow.
- **Edge:** defines the next step after a node finishes.
- **Conditional edge:** chooses a path based on a value in graph state.
- **State:** data passed between the nodes.
- **Structured output:** model output validated against a schema instead of relying on free-form prose.
- **Tool calling:** an LLM returns a structured request to invoke a predefined Python function.

---

## 5. How LangGraph state works here

The state definitions are in `Models/schema.py`.

### 5.1 Main router state

`DataAgentSchema` contains:

- `messages`: the list of user/agent messages.
- `route_response`: the selected route, `sql` or `etl`.

Its `messages` field is annotated with `Annotated[list, add]`. The `add` reducer describes list accumulation when LangGraph merges updates to this field. The code also manually concatenates messages in several nodes, so it is important to understand the actual node return/update behaviour rather than assume each list is automatically replaced.

### 5.2 SQL state

`AgentSchema` explicitly carries the SQL pipeline's intermediate results:

| Field | Why it exists |
|---|---|
| `user_question` | Original question |
| `curated_ques` | Refined question |
| `prompt_query_context` | Question + schema context passed to SQL generation |
| `generated_sql_query` | Proposed SQL string |
| `is_safe` | `Yes` / `No` safety decision |
| `comments` | Safety judge's explanation |
| `sql_query_execution_result` | Returned database result |
| `final_answer` | User-facing response |
| `messages` | Conversation output |

A key benefit is observability: intermediate state makes it possible to inspect which query was generated, whether it was judged safe, and what result was returned.

### 5.3 ETL state and structured router/judge results

- `ETLAgentSchema` stores the ETL agent's `messages`.
- `RouterSchema` constrains the router's answer to `sql` or `etl`, with a comments field.
- `JudgeSchema` constrains the SQL safety judge's answer to `Yes` or `No`, with comments.

These are Pydantic models. They improve structure and validation of outputs, but they do not automatically make generated SQL safe or generated Python code safe.

---

## 6. Main agent: routing workflow

The router is implemented in `agents/data_agent.py`.

### 6.1 Step-by-step flow

~~~mermaid
sequenceDiagram
    actor User
    participant Main as main.py
    participant Router as Data Agent
    participant LLM as Router LLM
    participant SQL as SQL Analyst graph
    participant ETL as ETL Analyst graph

    User->>Main: Natural-language question
    Main->>Router: invoke({messages, route_response})
    Router->>LLM: Classify latest message
    LLM-->>Router: RouterSchema {answer, comments}
    alt answer = sql
        Router->>SQL: invoke(SQL state initialized from question)
        SQL-->>Router: SQL graph state/result
    else answer = etl
        Router->>ETL: invoke({messages: [HumanMessage(question)]})
        ETL-->>Router: ETL graph state/result
    end
    Router-->>Main: Updated main state
    Main-->>User: Print returned state
~~~

### 6.2 What happens in `router_node`?

1. It reads the latest message's `content`.
2. It invokes an LLM configured with `with_structured_output(RouterSchema)`.
3. It extracts the structured `answer` value.
4. It writes that route into the graph state.

This is more reliable than parsing a free-form answer such as “I think this is probably a SQL question,” because the intended output is constrained to two route labels.

### 6.3 Conditional dispatch

After the router node, a conditional edge checks `route_response`:

- `sql` → `sql_node`
- `etl` → `etl_node`
- Any other value → raises a `ValueError`

The SQL branch initializes all SQL state fields and invokes `sql_analyst`. The ETL branch passes the user question to `etl_analyst`.

**Interview point:** the router is responsible for choosing the specialised workflow. It does not itself fetch data, execute SQL, or transform files.

**Implementation note:** in the code, `etl_node` and `sql_node` append the sub-agent response to `state.messages` manually, while the schema also defines a list-add reducer. If message accumulation is changed, verify that it does not duplicate messages.

---

## 7. SQL analyst workflow

The SQL agent in `agents/sql_analyst.py` turns a natural-language analytics question into a database query, applies a model-based safety decision, executes the query, and writes a readable answer.

### 7.1 The full SQL graph

~~~mermaid
flowchart TD
    Start([START]) --> C["curate_ques"]
    C --> SC["prompt_query_context"]
    SC --> G["generate_sql"]
    G --> J["is_safe_sql"]
    J --> D{Safety judge says Yes?}
    D -->|Yes| X["execute_sql"]
    D -->|No| Stop["canceled_sql"]
    X --> F["represent_final_answer"]
    F --> End([END])
    Stop --> End
~~~

### 7.2 Node-by-node explanation

#### Node 1 — `curate_ques`

The function calls the low-level model to refine the user's question. The idea is to make vague or awkwardly phrased requests clearer before SQL generation. It saves the curated question in state and appends it as a `HumanMessage`.

For example, “users most riding” might be refined into “Find users with the highest number of rides.” The exact rewrite depends on the model.

#### Node 2 — `prompt_query_context`

This node creates a `DatabaseUtil` using the database configuration found in environment variables. It calls `schema_details("public")` and embeds table names, columns, data types, and sample rows into the prompt for SQL generation.

The schema is important context because a model cannot reliably generate correct SQL without knowing the available tables and columns.

#### Node 3 — `generate_sql`

The medium-level LLM receives the constructed prompt and generates SQL. The prompt requests SQL only, and normally asks for a `LIMIT 10` unless the user specifies a row count.

The resulting string is written to `generated_sql_query`.

#### Node 4 — `is_safe_sql`

A medium-level LLM with `JudgeSchema` structured output assesses whether the SQL should be used only for data retrieval. The graph stores the judge's `Yes` / `No` result and its comments.

#### Conditional edge — Execute or cancel

- If `is_safe` is `Yes`, move to `execute_sql`.
- Otherwise, move to `canceled_sql`, which stores an explanation and appends it as an assistant message.

#### Node 5 — `execute_sql`

The generated query is passed to `DatabaseUtil.execute_sql()`, and its result is saved in state.

#### Node 6 — `represent_final_answer`

The low-level model receives the query result and curated question. It is instructed to produce a concise, user-friendly answer rather than a dump of SQL internals.

### 7.3 Example SQL request

User asks:

> “Show me the average rating for each vehicle type.”

The intended path is:

1. Refine the question.
2. Read schema details, including `ratings`, `rides`, and `vehicles` relationships.
3. Generate a query that joins the required tables and groups by the appropriate vehicle attribute.
4. Have the safety judge inspect the query.
5. Execute the query if approved.
6. Format the database rows into an understandable answer.

The exact SQL should be based on the schema and actual column names; the above is a workflow illustration rather than a guaranteed generated query.

### 7.4 Important SQL implementation caveats

The current safety step uses an LLM judge rather than a strict SQL parser or database-enforced read-only role. That judge can make mistakes. The database utility executes the query string with `cursor.execute(query)`, then calls `fetchall()` and `commit()`. It does not itself enforce a read-only transaction or statement allowlist.

The schema utility also builds a sample-row query by interpolating the schema/table identifiers into SQL. Those identifiers should be safely quoted, for example with `psycopg2.sql.Identifier`, and schema-column inspection should scope to the intended schema.

These details matter: **an LLM-based safety classification is a useful layer, not a hard security boundary**. For production, use a read-only database role, enforce SELECT-only SQL through parsing/policy checks, use statement timeouts and row limits, and safely handle errors and connections.

---

## 8. ETL analyst workflow

The ETL workflow is implemented in `agents/etl_analyst.py`. It exposes two model-callable tools and loops between an LLM node and a tool node until the model produces a message without tool calls.

### 8.1 ETL graph

~~~mermaid
flowchart TD
    Start([START]) --> LLM["llm_node<br/>LLM with ETL tools bound"]
    LLM --> ToolDecision{Latest AI message<br/>contains tool calls?}
    ToolDecision -->|Yes| T["tool_node"]
    T --> Result["Append ToolMessage observations"]
    Result --> LLM
    ToolDecision -->|No| End([END])
~~~

### 8.2 Tool 1 — `extract_load_tool`

The schema asks the model to supply:

- `url`: the API endpoint.
- `output_folder`: the destination folder.
- `format`: the desired output format.

The tool creates an `ETLTools` instance and calls `extract_load()`.

The implementation:

1. Calls `requests.get(url)`.
2. Calls `raise_for_status()` so unsuccessful HTTP status codes raise an exception.
3. Parses the response as JSON.
4. Normalizes `data['results']` with `pandas.json_normalize()`.
5. Ensures the destination directory exists.
6. Writes the resulting DataFrame to CSV, JSON Lines, or Parquet.

Supported format labels in the utility are `csv`, `json`, and `parquet`.

**Implementation note:** this particular extractor assumes the JSON response has a top-level `results` key containing an array-like collection. APIs with different response structures need a normalizer adapted to their shape. The HTTP request has no explicit timeout in the current code. Also, the project root is calculated relative to the `utils` directory, so its output path behaviour should be checked against the repository's intended top-level `data/` directory.

### 8.3 Tool 2 — `transform_load_tool`

The tool accepts the input file path, output folder, output format, and original user request.

The function then:

1. Loads the input file using `transform_load_context()`.
2. Reads up to three rows for prompt context.
3. Asks the configured Claude integration to generate Pandas code for the requested transformation.
4. Removes basic Markdown code-fence decoration.
5. Calls `ETLTools.execute_code()` to run the generated code.
6. Returns a string containing the generated code and execution status.

The expected transformations might include filtering rows, calculating aggregates, changing columns, or writing to a different file format. The LLM creates the code for the specific task, rather than the application implementing a fixed transformation for every possible question.

~~~mermaid
sequenceDiagram
    actor User
    participant Router as Data Agent
    participant ETL as ETL Analyst
    participant LLM as ETL LLM
    participant Tools as ETLTools
    participant Source as API / local file
    participant Output as Output file

    User->>Router: Request extraction or transformation
    Router->>ETL: Invoke ETL graph
    ETL->>LLM: Prompt + tool definitions
    LLM-->>ETL: extract_load_tool or transform_load_tool
    ETL->>Tools: Invoke requested tool
    alt API extraction
        Tools->>Source: HTTP GET
        Source-->>Tools: JSON response
        Tools->>Tools: Normalize JSON with Pandas
        Tools->>Output: Write CSV / JSON Lines / Parquet
    else File transformation
        Tools->>Source: Read CSV / JSON Lines / Parquet
        Source-->>Tools: Sample rows
        Tools->>LLM: Request Pandas transformation code
        LLM-->>Tools: Generated Python code
        Tools->>Tools: Execute generated code
        Tools->>Output: Expected output path from generated code
    end
    Tools-->>ETL: Tool result
    ETL->>LLM: Tool result in message history
    LLM-->>ETL: Final response or another tool call
    ETL-->>Router: ETL state
~~~

### 8.4 How tool calling works here

The ETL model is bound to the two decorated functions with `llm.bind_tools(tools)`. The model can return structured tool calls. The `tool_node` creates a name-to-tool lookup, invokes each returned tool call, and appends a `ToolMessage` correlated with the tool-call ID. The graph then routes back to the LLM so it can interpret the result and either take another action or finish.

The model/tool loop is useful because the LLM can choose between extraction and transformation based on the request, and can use tool observations to decide whether further work is required.

### 8.5 Critical code execution distinction

The method named `execute_code()` uses Python's `exec(code)` in the main application process. This is **not a sandbox**. It gives generated code the permissions and access of the running process, subject to the Python runtime. A prompt that asks the model to produce only Pandas code does not technically prevent file-system access, subprocesses, network calls, or other unsafe operations.

The project README describes safe/sandboxed execution, but the inspected utility uses ordinary `exec()` without an operating-system isolation boundary. Do not claim that generated ETL code currently runs in a secure sandbox. It should not be used with untrusted input in a production environment until this is addressed.

---

## 9. ETL internals: extract, transform, load

ETL stands for:

- **Extract:** obtain data from an API or source file.
- **Transform:** normalize, filter, clean, join, or calculate using Pandas.
- **Load:** persist the output to the destination format.

### 9.1 Extraction in the current implementation

~~~mermaid
flowchart TD
    A[API URL] --> B[requests.get]
    B --> C[raise_for_status]
    C --> D[Parse response JSON]
    D --> E[Read data results key]
    E --> F[pandas.json_normalize]
    F --> G{Requested format}
    G -->|csv| H[to_csv]
    G -->|json| I[to_json: records, lines]
    G -->|parquet| J[to_parquet]
    H --> K[Return status string]
    I --> K
    J --> K
~~~

The `json_normalize` call flattens nested dictionaries into tabular columns. For example, a nested field may become a dotted column name, helping the API payload fit into a DataFrame.

JSON output is written with `orient="records", lines=True`, so each record is stored as one JSON object per line (JSON Lines / NDJSON style).

### 9.2 Transformation sequence

~~~mermaid
flowchart TD
    A[Input file path] --> B{Extension}
    B -->|.csv| C[pandas.read_csv]
    B -->|.json| D[pandas.read_json lines=True]
    B -->|.parquet| E[pandas.read_parquet]
    C --> F[Take first 3 rows for context]
    D --> F
    E --> F
    F --> G[LLM receives task + sample]
    G --> H[LLM generates Pandas code]
    H --> I[Light cleanup of code fences]
    I --> J[execute_code with exec]
    J --> K[Return execution status]
~~~

The sample of three rows gives the model a limited view of the data. It helps the model infer column names and types, but it may not describe all data conditions, missing-value patterns, or outliers.

### 9.3 Loading behaviour

In the extraction path, the utility explicitly controls the selected output format and writes the file. In the transformation path, the generated code is instructed in the prompt to save the DataFrame to the supplied output folder, but the application does not independently verify that the script actually wrote a file with the requested name and format before returning its success-oriented text.

**Production improvement:** separate data transformations from arbitrary generated code. One safer design is to have the model return a validated transformation specification (filters, selected columns, aggregations, joins, output settings), then let application-owned Pandas functions perform the operations. If general Python execution is unavoidable, isolate it using a disposable restricted container/process, resource limits, restricted file/network access, and timeouts.

---

## 10. PostgreSQL setup and data model

### 10.1 Why PostgreSQL?

The SQL analyst needs structured tables, relationships, typed columns, and joins. PostgreSQL stores the dataset in relational form so the agent can answer questions with SQL instead of manually loading entire CSVs for each request.

### 10.2 Sample schema created by `feed_db.py`

The seed script creates five tables under the `public` schema and loads the matching CSV files:

| Table | Main purpose | Relationships |
|---|---|---|
| `users` | Rider and driver/user profiles | Parent table for driver/rider references |
| `vehicles` | Vehicle make, model, year, driver | `driver_id → users.user_id` |
| `rides` | Ride times, endpoints, distance, fare, status | `rider_id` and `driver_id` → users |
| `payments` | Ride payment amount, method, status, transaction | `ride_id → rides`; `user_id → users` |
| `ratings` | Ride ratings, comments, and rated time | Links to ride, rider, driver |

The schema defines primary keys, foreign keys, selected unique constraints and indexes. It also includes a check that ratings are between 1 and 5.

~~~mermaid
erDiagram
    USERS ||--o{ VEHICLES : drives
    USERS ||--o{ RIDES : rides_as_rider
    USERS ||--o{ RIDES : rides_as_driver
    RIDES ||--o{ PAYMENTS : has
    USERS ||--o{ PAYMENTS : pays
    RIDES ||--o{ RATINGS : receives
    USERS ||--o{ RATINGS : submits_as_rider
    USERS ||--o{ RATINGS : receives_as_driver

    USERS {
        int user_id PK
        string first_name
        string last_name
        string email UK
        string user_type
        boolean is_active
    }
    VEHICLES {
        int vehicle_id PK
        int driver_id FK
        string make
        string model
        int year
        string license_plate UK
    }
    RIDES {
        int ride_id PK
        int rider_id FK
        int driver_id FK
        decimal distance_km
        decimal fare
        string status
    }
    PAYMENTS {
        int payment_id PK
        int ride_id FK
        int user_id FK
        decimal amount
        string payment_method
        string payment_status
    }
    RATINGS {
        int rating_id PK
        int ride_id FK
        int rider_id FK
        int driver_id FK
        int rating
    }
~~~

The diagram shows the logical foreign-key relationships as defined in the seed script. The schema does not imply that every business invariant (for example, whether a particular vehicle is valid for a given ride) is enforced at the database level.

### 10.3 What `feed_db.py` does

1. Loads environment variables using `load_dotenv()`.
2. Constructs a PostgreSQL connection from `host`, `port`, `user`, `password`, and `database`.
3. Creates the schema and tables if missing.
4. Truncates the five tables with `CASCADE` in the currently active code.
5. Loads each CSV using PostgreSQL's `COPY ... FROM STDIN` through `copy_expert`.
6. Prints record counts.
7. Commits the transaction and closes the cursor/connection.

**Important:** running `feed_db.py` clears existing rows from the target tables because the `TRUNCATE ... CASCADE` section is currently active, despite the surrounding comment saying it is optional. Use an expendable development database and confirm the configured database name before running it.

### 10.4 Database schema context

The SQL agent calls `DatabaseUtil.schema_details("public")` and includes table/column metadata plus up to five sample records from each table in the SQL-generation prompt. The sample data gives the model concrete examples, but it may also expose data values to the configured LLM provider. Sensitive datasets need suitable minimization and access controls.

---

## 11. Dynamic LLM selection

The function `pick_llm(level)` in `utils/llm_pick.py` centralizes model construction.

Current mappings in code:

| Level key | Provider integration | Configured model identifier | Usage in current workflows |
|---|---|---|---|
| `low` | `ChatOpenAI` | `gpt-5.6-luna` | Question curation and final answer generation |
| `medium` | `ChatOpenAI` | `gpt-5.6-terra` | SQL generation and SQL safety judge |
| `high` | `ChatOpenAI` | `gpt-5.6-sol` | Available mapping; not the main path in the inspected graph |
| `claude` | `ChatAnthropic` | `claude-sonnet-5` | Router and ETL analyst / transformation-code generation |

These are literal identifiers in the repository, not a guarantee that the provider account currently offers those exact model names. Successful execution depends on valid API keys and provider/model availability.

The design centralizes configuration and makes it easy to change the model choice. However, the helper currently maps by a caller-supplied level string; it does not compute complexity dynamically from tokens or the question content. The calling workflow chooses the level.

The trade-off is quality versus cost/latency. Cheaper/faster models can be used for small rewriting tasks, while the more capable selected model can handle routing or transformation decisions. This remains a heuristic chosen by the code.

---

## 12. End-to-end examples

### 12.1 Example A — “Show me the most common payment methods”

~~~mermaid
sequenceDiagram
    actor User
    participant Main as main.py
    participant Router as Data Agent
    participant SQL as SQL Analyst
    participant DB as PostgreSQL
    participant LLM as Final-answer model

    User->>Main: Ask about payment methods
    Main->>Router: Invoke router graph
    Router->>Router: Classify as sql
    Router->>SQL: Invoke SQL graph
    SQL->>SQL: Curate question
    SQL->>DB: Inspect schema and sample rows
    DB-->>SQL: Schema context
    SQL->>SQL: Generate SQL
    SQL->>SQL: Ask safety judge
    alt Judge says Yes
        SQL->>DB: Execute query
        DB-->>SQL: Query result
        SQL->>LLM: Format result for user
        LLM-->>SQL: Readable answer
    else Judge says No
        SQL->>SQL: Build refusal / safety explanation
    end
    SQL-->>Router: Updated SQL state
    Router-->>Main: Updated main graph state
    Main-->>User: Print response object
~~~

The SQL workflow is stateful: the query, judge outcome and database result are retained in the SQL state object. That makes it possible to debug which step produced a bad answer.

### 12.2 Example B — “Extract an API response into CSV”

1. The router classifies the message as `etl`.
2. The ETL analyst asks the LLM to choose a tool.
3. The model returns an `extract_load_tool` call with a URL, output folder, and format.
4. The Python function requests the API and parses JSON.
5. `pandas.json_normalize()` turns the `results` array into tabular rows.
6. Pandas writes `extracted_data.csv`.
7. The tool returns a status string, which is added as a `ToolMessage`.
8. The agent receives the observation and returns a final response.

### 12.3 Example C — “Filter rides to ratings above 4.5 and save as Parquet”

1. The router chooses ETL.
2. The ETL model requests `transform_load_tool`.
3. The helper reads the input file and supplies the first three rows as context.
4. The LLM generates Pandas code.
5. The current implementation executes that code with `exec()`.
6. Generated code is responsible for creating the intended output file.
7. The tool returns its code and execution status to the agent.

The transformation path should be described as **LLM-generated Python executed by the application**, not as a declarative transformation engine or an isolated sandbox. It also does not independently validate the file that the script claims to have written.

---

## 13. Security, correctness, and engineering trade-offs

An interview-ready understanding includes weaknesses and what you would improve.

| Area | Current implementation | Improvement |
|---|---|---|
| SQL safety | LLM judge decides whether generated SQL is safe | Add SQL parsing/allowlisting, enforce a read-only PostgreSQL role, use transaction/statement timeouts, and apply row limits at execution time |
| Generated ETL code | `exec(code)` in the application process | Replace with validated transformation specifications or execute in a strongly isolated disposable sandbox |
| API extraction | `requests.get(url)` without explicit timeout or host allowlist | Add connect/read timeouts, response size limits, retry policy, HTTPS/host allowlist and SSRF protections |
| Filesystem paths | LLM supplies input and output paths for ETL | Resolve paths under an allowed data directory and reject traversal/out-of-scope locations |
| Database credentials | Environment variables are used, but a hard-coded example connection exists at module scope in `utils/database.py` | Remove the hard-coded connection/write-to-file example from import time; load and validate configuration explicitly |
| Schema prompt privacy | Schema context includes up to five sample rows per table | Minimize/sanitize sample values and avoid sending PII/secrets to an LLM |
| SQL context correctness | Column inspection query filters by table name without also filtering schema name | Scope introspection by both schema and table; use correct identifier quoting |
| Error handling | Utility methods sometimes catch exceptions and return `None`/status text | Use structured error results; distinguish failure from successful empty results |
| ETL success reporting | Transformation tool constructs a success-oriented message even if `execute_code` returned a failure string | Make status machine-readable, stop on failure, and verify the output artifact exists |
| JSON API assumptions | Extractor expects top-level `results` | Define response-shape handling or make extraction configuration explicit |
| Seed database reset | `feed_db.py` currently truncates tables with cascade | Put destructive reset behind an explicit opt-in flag and require confirmation/environment checks |
| Dependency/config alignment | README, pyproject, requirements, and model IDs can drift | Test a clean install; keep environment docs and dependency metadata aligned |

### 13.1 Why an LLM safety judge is not enough

A second model can reject obviously dangerous statements, but it is still a probabilistic classifier. It can misunderstand SQL, be influenced by misleading context, or miss database-specific behaviour. The final enforcement should not depend solely on model judgment.

A safer layered design is:

1. Generate the SQL.
2. Parse it and enforce an explicit policy (for example, a single read-only SELECT statement).
3. Execute with a database user that has only SELECT permissions.
4. Enforce execution timeout, result-size cap, and query logging.
5. Format the result only after successful execution.

### 13.2 Why plain `exec()` is dangerous

The transformation code originates from a model and is executed as Python in the current process. Python `exec()` does not restrict code to Pandas operations. Generated code can potentially access files, import modules, make network requests, or consume excessive resources with the permissions of the running process.

For a safer alternative, have the LLM output a structured plan such as:

```json
{
  "source": "data/rides.csv",
  "filters": [{"column": "rating", "operator": ">", "value": 4.5}],
  "group_by": [],
  "aggregations": [],
  "output_format": "parquet"
}
```

The application can validate this specification against allowed columns/operators, build the Pandas operations itself, and write output only beneath a controlled directory. This is an example of a recommended future design, not the format the current implementation uses.

### 13.3 Import-time database work

At the bottom of `utils/database.py`, the module constructs a database utility with literal connection details, calls schema inspection, and writes `test_schema_details.txt`. Because these statements run at module import time, importing the module can cause an unexpected connection attempt and file write, in addition to the explicit work performed by the agent. Move this demonstration into a guarded `if __name__ == "__main__":` block and remove hard-coded credentials.

---

## 14. Configuration and running the project

### 14.1 Environment variables

The checked-in `.env.example` currently provides these names:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Authentication for the OpenAI-compatible model client |
| `ANTHROPIC_API_KEY` | Authentication for the Anthropic client |
| `host` | PostgreSQL host |
| `port` | PostgreSQL port |
| `user` | PostgreSQL username |
| `password` | PostgreSQL password |
| `database` | PostgreSQL database name |

Use real local values in an untracked `.env` file. Never put real credentials into this documentation or commit them. Confirm that the configured database is the intended development/test database before using `feed_db.py`.

### 14.2 Expected setup path

The checked-in project metadata requires Python 3.12 or newer.

A typical local setup is:

```bash
# From the repository root
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux (use this instead of the Windows activation command)
# source .venv/bin/activate

# Install dependencies using pip
python -m pip install -r requirements.txt
```

Alternatively, install the project using the package manager supported by your environment and `pyproject.toml`. The repository includes `uv.lock`; if using uv, install uv first and then use the appropriate `uv sync` workflow.

Next:

1. Start PostgreSQL and verify connectivity.
2. Create a local `.env` with the correct database and LLM credentials.
3. Review the destructive `TRUNCATE` statements in `feed_db.py`.
4. Run `python feed_db.py` only against an intended local/test database to create tables and load sample CSVs.
5. Run `python main.py` to invoke the example data-agent workflow.

The checked-in `main.py` is an example invocation, not a persistent interactive chat server. It creates one hard-coded sample request, invokes the graph, and prints the resulting state.

### 14.3 Common failure points

| Symptom | What to check |
|---|---|
| Missing API key | Check `.env`, variable spelling, and whether the provider requires a different credential |
| PostgreSQL connection error | Check server state, host, port, database name, credentials, and user permissions |
| Relation/column not found | Run the seed process in the correct database and inspect the actual schema |
| SQL judge rejects query | Inspect `generated_sql_query` and `comments` in the returned SQL state |
| API request fails | Check endpoint URL, network, rate limits, timeout policy, and expected JSON shape |
| Unsupported input extension | The transform context loader currently supports CSV, JSON Lines-style JSON, and Parquet |
| Parquet dependency issue | Confirm PyArrow is installed in the active virtual environment |
| Generated transformation reports failure | Inspect the generated code and execution result; current tool output may still use success-oriented wording |

---

## 15. Interview walkthroughs and questions

### 15.1 “Explain Analyst.Jr in 90 seconds”

> Analyst.Jr is a Python-based agentic data analyst built with LangGraph and LangChain. It accepts natural-language requests and routes them to one of two specialised workflows: a SQL analyst for PostgreSQL questions, or an ETL analyst for API extraction and file transformation.
>
> The main data agent uses structured output to classify the latest user message as SQL or ETL. The SQL graph refines the question, gathers schema context, asks an LLM to generate SQL, requests a separate model-based safety decision, executes the approved query, and formats the result. The ETL graph binds two tools—extract/load and transform/load—and loops between the LLM and tool node until it can return a final response.
>
> The ETL utility uses Requests and Pandas to normalize API JSON and write CSV, JSON Lines, or Parquet. The transformation flow uses an LLM to generate Pandas code, which the current implementation executes using Python `exec()`. I would strengthen this before production by enforcing SQL read-only access, replacing unrestricted generated-code execution with a validated transformation plan or isolated sandbox, and improving validation, error handling, path controls, and observability.

### 15.2 “Walk me through a SQL query”

1. `main.py` passes the question as a `HumanMessage`.
2. `data_agent.py` invokes the structured router and receives `sql`.
3. `sql_node` initializes an `AgentSchema` and calls the SQL graph.
4. `curate_ques` refines the question.
5. `prompt_query_context` retrieves database schema details.
6. `generate_sql` generates a query using the medium-level model.
7. `is_safe_sql` obtains a structured `Yes`/`No` decision.
8. A conditional edge sends the workflow to execution or cancellation.
9. On approval, `execute_sql` uses `DatabaseUtil` to run the query.
10. `represent_final_answer` produces the user-facing response.

### 15.3 “Walk me through ETL”

1. The router classifies the request as ETL.
2. The ETL graph sends the conversation to an LLM bound to `extract_load_tool` and `transform_load_tool`.
3. A returned tool call is executed by `tool_node`.
4. Extraction uses Requests, parses the API JSON, normalizes the `results` array, and writes the requested output format.
5. Transformation reads the local file, gives sample rows and the user's request to an LLM, then executes generated Python through `exec()`.
6. The tool result is appended as a `ToolMessage`.
7. The graph returns to the LLM; a further tool call loops back to tools, while no tool calls ends the graph.
8. The resulting state returns through the main data agent.

### 15.4 Common interview questions

**Why use LangGraph instead of one long function?**  
The graph makes the flow explicit: the SQL path is a fixed sequence with a conditional safety branch, while the ETL path has a tool-call loop. Each node has one responsibility, and state holds intermediate data for inspection.

**Why use structured output for the router?**  
It constrains the route to valid labels (`sql` or `etl`), which makes conditional routing less fragile than interpreting free-form text.

**What does the SQL safety judge do? Does that guarantee safety?**  
It provides a model-based decision and explanation; it does not guarantee safety. Strict query validation and read-only database permissions are necessary independent controls.

**How does schema context improve SQL generation?**  
It supplies table/column names, types, and sample values so the model can use real schema information rather than invent columns.

**What is `pandas.json_normalize()` used for?**  
It flattens nested JSON structures into DataFrame columns, making semi-structured API data easier to transform or save as a tabular format.

**How does tool calling work in the ETL graph?**  
The LLM chooses a predefined tool and structured arguments. The tool node invokes the Python function, wraps its observation in a `ToolMessage`, and returns control to the LLM.

**Is the generated ETL code sandboxed?**  
Not in the inspected code. It is executed through `exec()` in the current process. This is a major security limitation and should be fixed before untrusted use.

**Does the model selector estimate query difficulty?**  
Not automatically. The current caller chooses a level such as `low`, `medium`, or `claude`, and `pick_llm()` constructs the corresponding client.

**Why PostgreSQL rather than querying CSVs directly?**  
PostgreSQL supports typed relational tables, keys, indexes, joins, and repeatable SQL analytics. CSV files are suitable for source datasets and ETL output, whereas PostgreSQL is the queryable relational store for the SQL branch.

**How would you make the project more robust?**  
Use read-only database roles and strict SQL validation, replace `exec()` with typed ETL specifications or strong sandboxing, validate file paths and API targets, add timeouts and resource limits, improve structured errors, and test both graph paths plus failure conditions.

---

## 16. Glossary and revision checklist

### Glossary

| Term | Meaning |
|---|---|
| Agentic workflow | A workflow where an LLM can choose actions or tools as part of solving a task |
| LangGraph | A framework for defining stateful workflows with nodes, edges, and conditional branches |
| StateGraph | The graph builder used to register nodes and transitions |
| Router | Classifies the user's intention and selects a specialised sub-agent |
| SQL generation | Producing a SQL query from a natural-language question |
| Schema context | Table/column metadata and sample rows included in the SQL prompt |
| Structured output | Model output that conforms to a defined schema |
| Tool binding | Exposing specific Python functions to the model as callable tools |
| ToolMessage | A message that records the result of a tool call |
| ETL | Extract, Transform, Load |
| `json_normalize` | Pandas utility for flattening nested JSON into tabular data |
| CSV | Comma-separated values format for tabular data |
| JSON Lines | Format where each line is a separate JSON record |
| Parquet | Columnar data file format commonly used in analytics |
| Read-only database role | Database account that cannot modify data or schema |
| Sandbox | An isolated execution environment with restricted privileges/resources |
| SSRF | Server-side request forgery: abuse of a server's network requests to reach unintended destinations |

### Before the interview, make sure you can explain

- [ ] Why the main agent needs routing.
- [ ] What `RouterSchema` validates and how conditional edges dispatch requests.
- [ ] Every node of the SQL graph and the order in which they run.
- [ ] How schema details enter the SQL-generation prompt.
- [ ] Why a model-based SQL judge is not a sufficient security boundary.
- [ ] What each of the two ETL tools accepts and returns.
- [ ] How API JSON becomes a CSV, JSON Lines file, or Parquet file.
- [ ] How the ETL tool-call loop returns observations to the LLM.
- [ ] How `feed_db.py` creates the tables and ingests CSV files.
- [ ] What `pick_llm()` does and what its level argument actually controls.
- [ ] Why Python `exec()` is dangerous and how you would replace or isolate it.
- [ ] The main failure paths and the improvements you would prioritize.

---

<div align="center">

**The core workflow to remember**

**Understand request → Route → Gather context → Generate action → Validate → Execute → Format result**

</div>

This guide reflects the inspected source code. When presenting the project, distinguish implemented behaviour from recommended improvements—especially for SQL enforcement and generated-code execution.

