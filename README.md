# OpenAI with SAP

## Use cases

* Use case #1: Text to SQL
* [Use case #2: Use your own data with Azure OpenAI service](https://github.com/thzandvl/sap-ai-docs)

## Use-case #1: Text to SQL

Converting text to SQL using OpenAI's GPT-4 and Azure Synapse.

One of the use-cases of ChatGPT is Natural Language Processing. As in my work I am looking for use-cases how we can integrate Azure Services with SAP workloads, one of the easiest ways is by simply converting text into SQL. TSQL in this specific case as I will be integrating with Azure Synapse.

### Prerequisites

* `Extract data`: The assumption here is that you already extracted SAP data into Azure Synapse. If not, please follow the steps in this [microhack](https://github.com/thzandvl/microhack-sap-data) to do so. If you do have the proper HANA Enterprise License you could also directly use the SQL queries on the HANA database.\
As a dataset I will, just like in the microhack, use Sales Order Items, Sales Order Headers and Payments data.
* `OpenAI deployment`: An OpenAI deployment on Azure is required. For more information on how to create an OpenAI deployment please visit the [documentation](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal). For this test I used the GPT-4 model.
* `Azure Functions`: For the code I will use the Python programming model v2. For more information on Azure Functions please visit the [documentation](https://learn.microsoft.com/en-us/azure/azure-functions/create-first-function-vs-code-python?pivots=python-mode-decorators).
* `ODBC driver`: For the connection to the Azure Synapse database I will use the ODBC driver. For more information on the ODBC driver please visit the [documentation](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver18). I used the latest version, at this moment this is version 18.

### The code

The code only exists of two functions. One to receive the prompt and the other to convert the text to SQL.

#### The prompt

This is mainly the default function generated while creating the Azure Function. The only thing I changed is the route and the name of the function.

```python
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
        logging.info('Returning the result')
        return func.HttpResponse(result, status_code=200)
     else:
        return func.HttpResponse(
             "Pass a prompt in the query string or in the request body for the correct result.",
             status_code=200
        )
```

#### The conversion

This is where the magic happens. The function will first connect to the Azure Synapse database using the ODBC driver. It will then execute a query to retrieve the column names from the database. This information will be used to create the prompt for OpenAI. The prompt will be sent to OpenAI and the response will be used to create a SQL query. This query will then be executed on the Azure Synapse database and the result will be returned.

```python
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
        msgs = [
            {"role": "system", "content": 'You are an AI that converts natural language to SQL code'},
            {"role": "user", "content": prompt}
        ]
        logging.info(f"messages : {msgs}")

        # Setting API Key and API endpoint for OpenAI
        openai.api_type    = os.environ["OPENAI_TYPE"]
        openai.api_base    = os.environ["OPENAI_URL"]
        openai.api_version = os.environ["OPENAI_VERSION"]
        openai.api_key     = os.environ["OPENAI_API_KEY"]
        deployment_name    = os.environ["OPENAI_MODEL"]

        logging.info('Sending an SQL generation request to OpenAI')
        response = openai.ChatCompletion.create(
            engine=deployment_name,
            messages=msgs,
            temperature=0,
            max_tokens=200,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stop=["#",";"])
        
        logging.info('### RESPONSE FROM OPENAI ###')
        logging.info(json.dumps(response))

        # Retrieve the generated SQL Query
        sqlquery = f'SELECT {response.choices[0].message.content}'
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
```

Make sure to set the OS environment variables in `local.settings.json` for local testing and in the Azure Function App settings for the deployment. The following variables are required:

* `OPENAI_TYPE`: The type of API you are using. This is `azure` in this case.
* `OPENAI_URL`: The API endpoint. The URL to your OpenAI deployment in the format `https://<deployment-name>.openai.azure.com/`
* `OPENAI_VERSION`: The API version. I used `2023-07-01-preview`.
* `OPENAI_API_KEY`: The API key you received from OpenAI.
* `OPENAI_MODEL`: The name of the model you want to use. As I use the GPT-4 model I used the name of my GPT-4 deployment.

### Testing the code

In my local deployment I used the following REST query:

```http
POST http://localhost:7071/api/prompt
content-type: application/json

{ "prompt": "What is the monthly average of the payments over the year 2019?" }
```

The result from OpenAI is:

```json
{
    "choices": [
        {
            "content_filter_results": {
                "hate": {
                    "filtered": false,
                    "severity": "safe"
                },
                "self_harm": {
                    "filtered": false,
                    "severity": "safe"
                },
                "sexual": {
                    "filtered": false,
                    "severity": "safe"
                },
                "violence": {
                    "filtered": false,
                    "severity": "safe"
                }
            },
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "content": "MONTH(PaymentDate) AS Month, AVG(PaymentValue) AS AveragePayment\nFROM Payments\nWHERE YEAR(PaymentDate) = 2019\nGROUP BY MONTH(PaymentDate)",
                "role": "assistant"
            }
        }
    ],
    "created": 1696863777,
    "id": "chatcmpl-87m4X3E6PAgeLvL00Y8FnLG25kpeo",
    "model": "gpt-4",
    "object": "chat.completion",
    "prompt_filter_results": [
        {
            "content_filter_results": {
                "hate": {
                    "filtered": false,
                    "severity": "safe"
                },
                "self_harm": {
                    "filtered": false,
                    "severity": "safe"
                },
                "sexual": {
                    "filtered": false,
                    "severity": "safe"
                },
                "violence": {
                    "filtered": false,
                    "severity": "safe"
                }
            },
            "prompt_index": 0
        }
    ],
    "usage": {
        "completion_tokens": 38,
        "prompt_tokens": 1263,
        "total_tokens": 1301
    }
}
```

The TSQL query is executed on the Azure Synapse Database and the REST query returns the following result:

```text
Question: What is the monthly average of the payments over the year 2019?
SQL Query: SELECT MONTH(PaymentDate) AS Month, AVG(PaymentValue) AS AveragePayment FROM Payments WHERE YEAR(PaymentDate) = 2019 GROUP BY MONTH(PaymentDate)

Generated Response: [(10, Decimal('28603.836754')), (1, Decimal('11880.720000')), (5, Decimal('30499.114285')), (2, Decimal('44536.756097')), (7, Decimal('33671.885057')), (9, Decimal('25828.233333')), (8, Decimal('27832.259259')), (3, Decimal('24963.977011')), (12, Decimal('28635.140392')), (6, Decimal('55422.606060')), (11, Decimal('20982.842460')), (4, Decimal('29175.369318'))]
```

### Next steps

A good next step would be to make a chart based on the results, this could be done with WebPilot. Another improvement is to create a Power Virtual Agents bot that uses this Azure Function to answer questions about the data in the Azure Synapse database. This way you can create a chatbot that can answer questions about your data. I did this and integrated the PVA in Microsoft Teams.