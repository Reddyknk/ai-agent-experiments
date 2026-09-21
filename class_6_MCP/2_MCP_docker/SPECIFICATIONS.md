# SPECIFICATION:
Create a system of MCP including the server and client app.

## Server - People Info
- Put the code for the server side in the “PeopleInfo_Server”
- Put all the libraries needed by the code in the requirements.txt file
- Create a docker container with the tool that returns the name, city, country, and the position of one or more people who fit the criteria provided in the query.
    - The tool accepts 2 string parameters.
    - The first string, "search_for", is the first string.
    - The second parameter is the string "field_name", which represents the column to search.
    - The tool uses fuzzy search for the string that matches the query message and returns all the items that match the search.
    - Create the CSV document “employee_data.csv” with random person name and details that will be used for the data

## Server - Random Number
- Put all the files for the server side in the “RandomNum_Server” folder
- Put all the libraries needed by the code in the requirements.txt file
- Create a docker container that will act as MCP server with 2 tools.
    - The first tool, “rand_int”, accepts 1 integer “max_number” parameter and responds with a random number from 1 to the number provided in the parameter received.
    - The second tool, “rand_real”, accepts no parameters and returns a random real number from 0 to 1.

## Client
- Put the code at the root folder
- Put all the libraries needed by the code in the requirements.txt file
- Create the client side app that goes through the real steps for MCP client service
    - The app first check whether the servers are running. If not, start them using the docker-compose.yml file.
    - Go through the proper steps to connect to the MCP server.
    - Show a prompt in the text console with the list of tools that are available in the MCP server.
        - List one tool per line
        - Each line shows a number starting with 1, the tool name, and the MCP server name
        - The last item is the option to “Quit” the app
    - When the user selects a number, display the parameters required by the tool
    - The user enters the parameters separated by commas
    - When the user hits <enter>, make the call to the MCP server then print the formatted raw message to the server and the formatted raw response from the server to the console.
    - Show the prompt for the user to select the tool again.

## Other Requirements
- Create all the files to deploy the two docker containers
- Create the README.md file with the details about what the app does, how it works, and how to set up and run the system
  - Include the instruction on how to install all the necessary components to run Docker on Linux, MacOS, and Windows PC
  - Add instructions how to build and run the containers
