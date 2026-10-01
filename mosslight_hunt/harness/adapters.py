"""Runtime provider adapters. Importing this module never contacts a provider."""
import json
import os
import urllib.request

class BraveSearch:
    """Optional narrow host proxy; tool containers have no general network."""
    def __call__(self, query, seconds):
        from urllib.parse import urlencode
        if not isinstance(query,str) or not 1 <= len(query) <= 1000:
            raise ValueError("search query must contain 1–1000 characters")
        request=urllib.request.Request("https://api.search.brave.com/res/v1/web/search?"+urlencode({"q":query,"count":5}),headers={"X-Subscription-Token":os.environ["BRAVE_SEARCH_API_KEY"],"Accept":"application/json"})
        with urllib.request.urlopen(request,timeout=min(15,max(.01,seconds))) as response:
            result=json.load(response)
        return {"results":[{"title":r["title"],"url":r["url"],"description":r.get("description","")} for r in result.get("web",{}).get("results",[])]}

class OpenAISearch:
    """Stateless Responses web-search proxy using the existing OpenAI credential."""
    def __init__(self, model="gpt-4.1"):
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY is required for OpenAI web search")
        self.model=model
    def __call__(self, query, seconds):
        if not isinstance(query,str) or not 1 <= len(query) <= 1000:
            raise ValueError("search query must contain 1–1000 characters")
        body={"model":self.model,"tools":[{"type":"web_search"}],"tool_choice":"required",
              "max_output_tokens":1500,"store":False,"input":"Search public documentation and return concise cited findings for: "+query}
        request=urllib.request.Request("https://api.openai.com/v1/responses",data=json.dumps(body).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+os.environ["OPENAI_API_KEY"]})
        with urllib.request.urlopen(request,timeout=min(30,max(.01,seconds))) as response:
            result=json.load(response)
        content=[part for item in result.get("output",[]) if item.get("type")=="message" for part in item.get("content",[]) if part.get("type")=="output_text"]
        return {"text":"\n".join(part["text"] for part in content),"citations":[annotation for part in content for annotation in part.get("annotations",[]) if annotation.get("type")=="url_citation"]}
