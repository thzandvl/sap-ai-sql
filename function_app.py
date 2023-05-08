import azure.functions as func
import logging, os
import openai, json, pyodbc

# SQL info
server = os.environ['SQL_URL']
database = os.environ['SQL_DB']
username = os.environ['SQL_USER']
pwd = os.environ['SQL_PASS']

app = func.FunctionApp()

# Retrieve the prompt and return the SQL result
@app.function_name(name="ProcessPrompt")
@app.route(route="prompt", auth_level=func.AuthLevel.ANONYMOUS)
def processPrompt(req: func.HttpRequest) -> func.HttpResponse:
     logging.info('Python HTTP trigger function processed a request.')

     prompt = req.params.get('prompt')
     if not prompt:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            prompt = req_body.get('prompt')

     if prompt:
        result = generateSQL(prompt)
        logging.info('Return the result')
        return func.HttpResponse(result, status_code=200)
     else:
        return func.HttpResponse(
             "Pass a prompt in the query string or in the request body for the correct result.",
             status_code=200
        )


# Get information about your data, and use it translate natural language to SQL code with OpenAI to then execute it on your data
def generateSQL(query):
    
    # Connect to your database using ODBC
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=' + server +';DATABASE=' + database + ';UID=' + username +';PWD=' + pwd + ';')

    try:
        # Execute the query to retrieve the column information
        with conn.cursor() as cursor:
            sql = "SELECT TABLE_NAME,COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS"
            cursor.execute(sql)
            result_set = cursor.fetchall()

            # Extract the column names from the cursor description
            column_names = [column[0] for column in cursor.description]

            # Extract the column names from each row and convert to dictionary
            result_list = [dict(zip(column_names, row)) for row in result_set]

        # Format the result set as a JSON string
        result_set_json = json.dumps(result_list)

        # Define the OpenAI prompt
        prompt = f"# Here are the columns in the database:\n# {result_set_json}\n### Generate a single T-SQL query for the following question using the information about the database: {query}\n\nSELECT"
        logging.info(prompt)

        # Setting API Key and API endpoint for OpenAI
        openai.api_type = "azure"
        openai.api_base = os.environ["OPENAI_URL"]
        openai.api_version = "2022-12-01"
        openai.api_key = os.environ["OPENAI_API_KEY"]

        deployment_name = os.environ["OPENAI_MODEL"]

        logging.info('Sending an SQL generation request to OpenAI')
        response = openai.Completion.create(
            engine=deployment_name,
            prompt=prompt,
            temperature=0,
            max_tokens=200,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stop=["#",";"])
        
        logging.info('### RESPONSE FROM OPENAI ###')
        logging.info(json.dumps(response))

        # Retrieve the generated SQL Query
        sqlquery = f'SELECT{response.choices[0].text}'
        sqlquery = sqlquery.replace("\n", " ")
        logging.info(f'SQLQuery: {sqlquery}')

        # Execute the SQL query
        cursor.execute(sqlquery)
        logging.info('Query executed')
        final_result = str(cursor.fetchall())
        logging.info('SQL result fetched')

        # Print the question + SQL Query + Generated Response
        return 'Question: ' + query + '\nSQL Query: ' + sqlquery + '\n\nGenerated Response: ' + final_result

    finally:
        conn.close()