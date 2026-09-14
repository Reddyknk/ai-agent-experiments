# Structured Multi-Skill AI Agent

This document details the modular layout, schemas, configurations, and core python runner infrastructure needed to build an autonomous agent containing domain-specific capabilities using the official google-genai SDK.

## 📂 Directory Architecture
The layout isolates domain procedural logic into standard structural boundaries:
```
antigravity-agent/
├── app.py                      # Core Orchestrator utilizing google-genai SDK
├── requirements.txt            # Package declarations
└── skills/
    ├── datetime-weather-skill/
    │   ├── SKILL.md            # Metadata & SOP for Skill 1
    │   └── scripts/
    │       └── env_tools.py    # Public Open-Meteo & Time logic (No Keys Req.)
    ├── house-registry-skill/
    │   ├── SKILL.md            # Metadata & SOP for Skill 2
    │   └── data/
    │       └── registry.csv    # Flat-file database for record resolution
    └── plant-care-skill/
        ├── SKILL.md            # Metadata & SOP for Skill 3
        └── templates/
            └── plant_info.md   # Plant care instructions template
```

## 🧱 Core Architecture Component Highlights

### 1. Skill 1: datetime-weather-skill

- **Control Manifest (SKILL.md)**: Contains YAML frontmatter outlining semantic keywords (weather, time), regular expression targets, and explicit tool binding declarations to pass to the dynamic execution layer.

- **Deterministic Execution Script (./scripts/env_tools.py)**: Bundles two critical python routines. It queries OpenStreetMap's Nominatim API using an open User-Agent string to parse any global string city into exact latitude and longitude boundaries, then feeds those coordinates directly to Open-Meteo to pull down real-time weather analytics safely without requiring a proprietary API key.

### 2. Skill 2: house-registry-skill

- **Local Asset Asset Map (./data/registry.csv)**: Implements a tabular comma-separated structure tracking explicit column schemas (name, city, country, house_color).
  - Create sample data for testing, e.g. "Smith,New York,USA,red".

- **Operational SOP**: Restricts the core orchestrator model to strict, case-insensitive containment scanning over the static database lines to completely block hallucinated data paths.

### 3. Skill 3: plant-care-skill

- **Control Manifest (SKILL.md)**: Contains YAML frontmatter outlining semantic keywords (plant-care, plant-info), regular expression targets, and explicit tool binding declarations to pass to the dynamic execution layer. Any mention of "plant", "plants", "care", "caring", "instructions", "information", etc. should trigger this skill.

- **Plant Care Instructions (./templates/plant_info.md)**: Contains template for the model to use to provide plant care instructions in markdown format. This format has already been provided in the `plant_info.md` file. The instruction is to add more details to the template to make it more comprehensive.

### 4. Execution Orchestrator (agent.py)

- Leverages from `google import genai` via the standard native SDK structure.

- Binds Python function structures natively using the `tools` parameter inside `types.GenerateContentConfig()`.

- The agent should use the LLM model to perform skill routing in the first turn and then use the tool calls to retrieve the data and respond to the user.

- Implements an asynchronous validation match over `response.function_calls` loops, executing the respective skill runtime pipeline and routing the generated parameters safely back into the final response synthesis stage.


### 5. Other requirements

- The app should have a web interface with 2 pages selectable from the buttons on the top of the page.
  - Page 1: Chat with Agent
    - There should be a drop down menu to select the model to use. The list should include Gemma 4 26B, Gemma 4 31B, Gemini 3.5 flash lite, Gemini 3.8 flash, and a place where user can enter the text manually. This selection should not be scrolled out of view when the user is scrolling through the chat history.
    - The page allows the user to chat with the agent and respond to user queries.
    - The chat should have a text input field and a send button.
    - The chat should display the conversation history.
  - Page 2: Log Review
    - The page allows the user to review the logs of the agent.
    - The logs should show 2 tables.
    - The first table should show all the conversations that happened between the user and the agent. There should be the following columns:
      - Conversation ID
      - Timestamp
      - User Query
      - Agent Response
    - When the row of the table is clicked, it should diplay the list of events that occurred during that conversation in the second table below.
    - The second table should display the following columns:
      - Timestamp
      - Event Type
      - Invoker
      - Target
      - Short Description
    - When the row is clicked, open a pop up window to show the detailed JSON logs in human readable format

- Impport API key and model name from `.env` file and use them to initialize the `genai` client.

- Create `logging.py` module to handle all logging operations.
  - It should log ALL of the Agent, LLM, and Tool ( including external APIs ) invocations in the `logs/` directory.
  - The log format should be JSON.
  - The log should contain the actual payload with all the fields passed or received from the model or tool invocation.
  - The API key in the payload should be redacted.
  - The log should be written asynchronously to the log file to avoid blocking the agent execution.

- Create `test_*.py` files to test all the functions in the `skills/` directory and the `agent.py` file and the final integrated agent.

- Create a `README.md` file to show how to run the agent and document its capabilities.


