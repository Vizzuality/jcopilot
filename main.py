from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import PlainTextResponse
from typing import Optional
from pydantic import BaseModel
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv
from jira import JIRA
from fastapi import BackgroundTasks
import json

app = FastAPI()

load_dotenv()
open_ai_token = os.getenv("OPEN_AI_TOKEN")
jira_url = os.getenv("JIRA_URL")
jira_email = os.getenv("JIRA_EMAIL")
jira_token = os.getenv("JIRA_TOKEN")
api_token = os.getenv("API_TOKEN")

class Project(BaseModel):
    id: int
    key: str
    name: str

class IssueFields(BaseModel):
    summary: Optional[str] = ""
    description: Optional[str] = ""
    project: Project

class Issue(BaseModel):
    id: int
    fields: IssueFields

class IssueData(BaseModel):
    issue: Issue

@app.get("/")
async def index():
    return PlainTextResponse("")

@app.get("/robots.txt")
async def robots_txt():
    return PlainTextResponse("User-agent: *\nDisallow: /")

def verify_token(authorization: Optional[str] = Header(None)):
    if authorization is None or not authorization.startswith("Bearer"):
        raise HTTPException(status_code=400, detail="Invalid token or token missing")

    token = authorization.split(" ")[1]  # Bearer token_value

    if token != api_token:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    return token

@app.post("/issue/")
async def receive_issue(background_tasks: BackgroundTasks, issue_data: IssueData, token: str = Depends(verify_token)):
    print(issue_data.dict())
    summary = issue_data.issue.fields.summary
    description = issue_data.issue.fields.description
    response_dict = await query_ai(summary, description)
    background_tasks.add_task(update_issue, response_dict["response"], issue_data.issue.id, description)
    return ("OK")

async def query_ai(summary: str, description: str):
    chat = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.5, openai_api_key=open_ai_token)

    question = f"issue: {summary}, {description}"
    
    system_m = '''
        As a Behaviour Driven Development agile software team, including roles such as product owner, project manager, lead QA tester, business analyst, and technical lead. You're tasked with managing a new Jira issue. The following steps are required:
        Create a succinct, clear summary distinct from other issues.
        Draft a detailed, understandable task description. Convey who is involved, what to do, and why it's beneficial. Use natural language, don't say explicitly "WHO", "WHY", and "What", not even jargon like "as a user"; write the description in a natural way. Add TBD for any missing details or information. Don't use vague adverbs like "fast", "easy", and be explicit; avoid examples or "such as". It's better to add TBD instead of vague terms.
        Generate acceptance criteria. Use 'Must' and 'Will' instead of 'should' or 'could'. Each criterion must reflect a single behavior.
        Alert of any detail that can be missed. 
        Alert of any possible bad practice
        Do any possible suggestion to simplify the task.
        Outline the testing flow for QA, including base flow, potential edge cases, and possible regressions, bot using natural language and using Gherkin.
        If needed, suggest creating subtasks for non-atomic tasks.
        Adhere to BDD practices. BDD aids in clear understanding of desired behavior, reducing confusion and assumptions, encouraging implementation discussions, and shedding light on potential implications or edge cases. Acceptance criteria should be outlined in user stories, which should be minimal and add functional value. Defining them before or during sprint planning ensures developers' understanding. Larger stories might need division to ensure completion within a sprint.
        Clear, testable criteria align expectations of non-technical personnel and developers, eliminate confusion, and promote a testing culture, leading to quality software with fewer regressions.
        Add potential subtasks if any.
    '''
    
    try:
        response = chat(
            [
                SystemMessage(content=system_m),
                HumanMessage(content=question)
            ])
        return {"response": response.content}
    except Exception as e:
        return {"error": str(e)}
    
async def update_issue(description, issue_id, original_description):
    jira_options = {'server': jira_url}
    jira = JIRA(options=jira_options, basic_auth=(jira_email, jira_token))
    issue = jira.issue(issue_id)
    if original_description:
        description = f"{description}, \n Original description:\n {original_description}"
    print (description)
    issue.update(fields={'description': description})