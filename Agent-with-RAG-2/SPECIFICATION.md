# Agent With RAG Specification
Build a web app to manage an AI Agent with RAG ability.

## 📂 Directory Architecture
The layout isolates domain procedural logic into standard structural boundaries:
```
Agent-with-RAG/
├── database/
├── samle_docs/
├── services/
├── skills/
│   ├── time-weather-skill/
│   │   ├── SKILL.md            # Metadata & SOP for Skill 1
│   │   └── scripts/
│   │       └── env_tools.py    # Public Open-Meteo & Time logic (No Keys Req.)
│   ├── person-information-skill/
│   │   ├── SKILL.md            # Metadata & SOP for Skill 2
│   │   └── data/
│   │       └── registry.csv    # Flat-file database for record resolution
│   └── stock-market-skill/
│       ├── SKILL.md            # Metadata & SOP for Skill 3
│       └── scripts/
│           └── stock_search.py   # Stock search tool
├── tests/                      # Store test files
├── app.py                      # Core Orchestrator
├── config.py                   # Configurable parameters
└── requirements.txt            # Package declarations
```

## GUI
The App should have 4 pages switchable with the tabs or buttons at the top of the window.
  - If the static/images folder has a file called tab-icon.gif, use it as the icon for the tab.
  - If the static/images folder has a file called app-icon.gif, put it on the left side of the App name at the top left of the window.
  - Add icon to the left of each tabs, cards and box names appropriate to the names.
  - At the same level as the tabs on the right side of the screen, put a button in the light red color “Shutdown” button.
    - When the user clicks this button, open a dialog box warning the user that this will shutdown the app and all the services. All the users will be affected by this action. Confirm by typing “Shutdown the service” in the text box.
    - Show two buttons in the dialog box: Cancel, and Confirm. The confirm box should be disabled until the user typed the exact word in the text box.
    - When the user click “Confirm” shutdown all the services started by the app. If some of the supporting services were running before the app started, do not shut them down.
  - To the left of the “Shutdown” button add a status box that shows the status of the backend Agent.
    - Periodically check the Agent API’s health and display the status of all the services needed to support the Agent.
  - The first page is called “Chat & Knowledge Synthesis”.
    - At the same level as the page title at the right side of the screen, put a drop down box showing the currently selected.
      - Check Google AI Studio for the active models that are capable of synthesizing and outputting text then list them in the dropdown. Include the option to select a custom model. When the Custom model is selected, show a text box for the user to enter the API Endpoint of the model. The default text should be the last endpoint entered. If none exists, put “http://127.0.0.1:8000/v1/chat/completions”.
      - To the left of the model choice dropdown, add a box to allow the user to select the “Temperature” parameter to send to the model.
      - To the left of the temperature box, add a text box to allow the user to set the “Max Tokens” parameter to send to the model. Do not allow the user to set the number larger than the max tokens of the model selected.
    - Below the page title, there should be two cards. The card on the left is the “Chat with the Agent”. Allow the user to type text to chat with the Agent.
      - Add the drop box to allow the user to select the maximum number of RAG chunks to send to the model.
      - Use a new conversation ID for each question 
      - Once the response is completed, display the response.
        - Add the detail box in the response with a button named “Show Logs”. Within the detail box, add bubbles showing the name of the components that generated the logs (such as Agent, Tools, RAG, Skills), icons appropriate for the components, and the elapse time of each step.
        - When the user clicks on the "Show Logs" button, the detail box should expand to show the full content of the step including the logs. Use scroll area in the bubble if the content is too long.
        - Make the "Show Logs" button toggle between expand and collapse.
        - Anchor "Show Logs" button at the top-right coner of the detail box.
    - The second card to the right displays “Retrieved Context Evidence” to display the contents of the information retrieved from the vector store. Group the info by the steps the information was retrieved. Ie: Skill Search, Document Search, etc
    - The width of both cards should be equal and they should fill the width of the page. The width should be approximately half of the screen width.
  - The second page “Vector DB Ingestion” allows the user to populate the Vector Database.
    - At the same level as the page title at the right side of the page, put the statistics of the ingestion. Display the number of chunks, documents ingested, and the size of the DB in MByte.
    - To the left of the statistic, add a button to “Update Skills Database”. When the button is selected, scan the skills/ folder and load new skills that are not in the skill database. Skills already in the database should not be loaded
    - To the left of the “Update Skills Database”, add a dropbox showing the list of Embedder that ollama can download.
      - Display the currently running model.
      - If the user selects a different model, display a pop up window with a stern warning to the user that changing the model will delete all the data currently in the database.
        - Show two buttons: Cancel and Delete Data (initially disabled).
        - Ask the user to type the text to confirm they want to change the model.
        - When the user typed the exact text, enable the “Delete Data” button.
        - When the user clicks “Delete Data”, proceed to delete the data in the document and skill databases, then make ollama to load the new model selected.
        - After the ollama completes updating the model, scan the skills/ folder and import the skills to the skill database
    - There should be two cards below the page title. The left card takes a url or local directory, then creates a private vector database from documents in the url or local directory and saves it to the database/ folder.
      - Provide 5 buttons for the user to click with samples of web URL that can be imported into the database.
      - Add a sub card called “Advanced Chunking Parameters” to allow the user to select the Chunk size and Overlap in the number of characters. The sub card should be collapsed by default.
      - Add the button at the bottom to populate vector database
      - When loading the database, make sure there is no duplicated chunk
    - The card to the right displays “Vector Storage Status”.
      - At the right side of the box put a button to allow the user to Reset the DB.
      - The card should show if the ingestion is in progress
      - It should also list the name of the document ingested and the number of chunks created and the total number of characters
    - The width of both cards should be equal and they should fill the width of the page. The width should be approximately half of the screen width.
    - Below the two cards, add another card to display the list of available Embedding Models for the embedding service. Briefly list the characteristics including the dimensions, context window, size, brief description, and status (Installed, Active, Available to Pull).
  - The third page is called Telemetry.
    - On the right side of the page, put the button called “Refresh Telemetry” to allow the user to manually refresh the page.
    - To the left of the “Refresh Telemetry” button, add a dropdown box to list the models that had been used. Filter the contents of the telemetry page based on the model selected. Include “All Models” as the default option.
    - Next, shows Total Prompts, Total Response, Total Errors, Total Input Tokens, and Total Output Tokens sent to and received from the LLM models.
    - Below the statistic, add a card that shows 2 graphs.
      - At the top of the box, there is a dropdown that selects the Aggregation/Refresh Interval with choices: 1 min, 15 min (default), 1 hr, and 1 day.
      - The second dropdown to the right allows the user to select the time range with options for: Last hr, 1 day (default), Week, Month and Custom. When Custom is selected, bring up two boxes with a dropdown calendar that allows the user to select the starting date and ending date.
      - Below the selection, the Left plot shows the line graphs of the number of prompts, responses and errors per Interval selected. The X-axis shows the time range selected.
      - The right plot shows the line graph of the number of input and output tokens per Interval selected. The X-axis shows the time range selected.
    - Another card below shows the text: “Other Important Statistic not Available for Low-Performance Computer”
      - Time to First Token (TTFT): The duration between a user sending a prompt and receiving the very first token. This is the most critical metric for perceived speed in streaming applications.
      - Inter-Token Latency (ITL): The average time elapsed between generating each subsequent token.
      - Tokens Per Second (TPS): The throughput speed of the model generation (often measured per request or aggregated across the server).
      - Time Per Output Token (TPOT): The total time taken to generate the response divided by the number of output tokens.
  - The fourth page should be called “Audit Log & Event”
    - To the right side of the page, add a button called “Refresh” to allow the user to manually refresh the page.
    - To the left of the “Refresh” button, add a button to allow the user to clear the logs. This will delete all the logs. When the user clicks on this box, open a pop up window asking the user to confirm.
    - Next, display the statistics of the total user prompts logged, model calls, Ollama embeds, Avg call latency.
    - Below the statistics, add a table listing all the user conversations in the log. Display the timestamp (in local time), conversation ID, User Query, Agent Response, Number of Events (occured during the conversation), etc. Display the total conversations in the table
      - Display at most 10 items and allow the user to scroll through all the items.
      - Allow the user to select the row
    - The next table displays all the logs associated with the conversation selected in the table above. The table should have columns showing the timestamp, Event Type, Invoker, Target, and short description of the log item.
      - Timestamp
      - Event Type
      - Invoker
      - Target
      - Short Description
      - When the row is clicked, open a pop up window to show all the detailed logs including the JSON payload in human readable format

## Requirements
- All of the backend code should be written in python, the web app should be built using flask.
- All calls to external resources like Google AI Studio or any external API should be done from the backend python code, not from the frontend.
- Use local ollama to vectorize the text.
- Upon start up, the app should check whether ollama is currently running and start the service if it is not already started.
- When the app terminates, shutdown the ollama service if the app started the service. If it is already running when the app starts, do not shutdown ollama.
- Upon start up, the app should scan the skills/ folder and load the skills that are not currently in the skills vector database.
  - The skills should have a separate skill vector database should be built as follow:
  - The contents from name and description fields should be sent to the Embedder/Vectorizer.
  - The vectors and the complete text of the SKILL.md file should be stored in the database as one record.
  - When the skill vector database is queried, the list of skills that have scores higher than MIN_SKILL_SCORE should be returned. The min score should be defined in config.py with the initial value of 0.5.
- On start up, get the list of ONLY active LLM models for text generation from Google AI Studio API that can be used by the agent. Use the list in the dropdown menu in the Chat page.
- Set DEFAULT_LLM_MODEL=gemma-4-26b-a4b-it in config.py as the default LLM model to use. Use this constant as the default everywhere the model is used.
- Create the following skills using the folder structure in the Directory Architecture. The skills should at least have the name, description, Trigger Queries, etc:
  - Get the time and weather of the city from the site that doesn't require API key
  - Get the list of stocks with the highest percentage increase or lowest percentage decrease based on the chat question
  - Get the list of text chunks from the document vector database. The score must  be higher than MIN_RAG_DOC_SCORE defined in config.py with the initial score of 0.3.
  - Get the name, city, country, or job title of the person in the CSV file.
    - Create 20 random samples of the CSV file with name, city, country, or job title for the tool to query
- If a skill matches with a score higher than MIN_SKILL_SCORE, make the call to the LLM with the skill with the highest score to get the instruction or plan for the tool execution.
- Only perform vector search for documents when the skill search result and the model direct the Agent to perform the search.

- Create 3 sample documents in the folder called sample_docs/.
  - One document should be about Agent and RAG technology,
  - The second document should be a sample of a company marketing strategy
  - The third document should be a sample of financial report for the company

- Create logs for all the invocations and responses between the following components. The log should include the actual details of the payloads passed to and from the components. Store the logs in the database/ folder in log.json file. The log should be in JSON format. Display in the same conversation event.
    - agent - full log of the message sent to the agent and the response received from the agent.
    - skill search - full log of the message sent to the skill search and the response received from the skill search. Include the name of the vectorizer and response from the vectorizer.
    - document search - full log of the message sent to the document search and the response received from the document search.
    - tool - full log of tool message passed to and received from the tool including the actual payload. If the tool makes external API call, log the full payload passed to the API and the full response received from the API.
    - ollama vector - log the first 50 characters of the text chunk sent for embedding. Include the name of the vectorizer and response from the vectorizer. Do not include the vectors.
    - LLM - prompts sent to and response received from the model include the FULL payload. Do not log the API call for model acces. Only log the model invocation and response with the FULL PAYLOAD.
    - In the log, include the time of the call, the type of the call, the invoker, the recipient, and all the raw payload passed in the message.
    - Do not combine the logs of from the request and response into the same log entry when displaying on the screen. Each invocation/response should be a separate entry in the log.
  - Redact API keys with “****” if any is present.
- Create a README.md with a brief description about:
  - what this system does
  - how to install the components needed
  - how to start all the services
  - how to shutdown all the services
  - user guide with information on how to use the system
