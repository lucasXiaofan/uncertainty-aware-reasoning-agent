import os
import subprocess
import requests

bash_tool = {
    "type": "function",
    "function": {
        "name": "bash_command",
        "description": "Execute bash/shell commands on macOS. Can create files, list directories, read files, etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute"
                }
            },
            "required": ["command"]
        }
    }
}

think_tool = {
    "type": "function",
    "function": {
        "name": "think",
        "description": "Continue internal reasoning and reflection before giving final answer. Use this to analyze, plan, or reconsider your approach.",
        "parameters": {
            "type": "object",
            "properties": {
                "thought": {
                    "type": "string",
                    "description": "Your internal thoughts, analysis, or reflection"
                }
            },
            "required": ["thought"]
        }
    }
}

brave_search_tool = {
    "type": "function",
    "function": {
        "name": "brave_search",
        "description": "Search the web using Brave Search API. Returns web search results with titles, descriptions, and URLs.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results to return (default: 10, max: 20)",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    }
}

ask_question_tool = {
    "type": "function",
    "function": {
        "name": "ask_question",
        "description": "Ask the patient a specific targeted question to gather critical missing information. This terminates the evaluation loop.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The specific question to ask the patient (should help differentiate between diagnoses)"
                },
                "confidence": {
                    "type": "number",
                    "description": "Your current confidence score (0-100) before asking this question"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of why this question is important for differential diagnosis"
                }
            },
            "required": ["question", "confidence", "reasoning"]
        }
    }
}

make_choice_tool = {
    "type": "function",
    "function": {
        "name": "make_choice",
        "description": "Make a final diagnosis choice when confidence is high (≥80%). This terminates the evaluation loop.",
        "parameters": {
            "type": "object",
            "properties": {
                "letter_choice": {
                    "type": "string",
                    "description": "The diagnosis letter choice (A, B, C, or D)",
                    "enum": ["A", "B", "C", "D"]
                },
                "confidence": {
                    "type": "number",
                    "description": "Your confidence score (0-100) in this diagnosis"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Detailed explanation of why this is the most likely diagnosis"
                }
            },
            "required": ["letter_choice", "confidence", "reasoning"]
        }
    }
}


def execute_tool(name: str, args: dict) -> str:
    if name == "bash_command":
        try:
            # macOS uses /bin/bash or /bin/zsh by default
            result = subprocess.run(
                args["command"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                executable='/bin/bash'  # or '/bin/zsh' if preferred
            )
            if result.returncode == 0:
                return f"Success:\n{result.stdout}" if result.stdout else "Success (no output)"
            else:
                return f"Error (code {result.returncode}):\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return "Error: Command timeout"
        except Exception as e:
            return f"Error: {str(e)}"
    
    elif name == "think":
        # Return acknowledgment, allowing agent to continue reasoning
        return f"Thinking Result: {args['thought']}.\nThought recorded. Continue thinking or provide final answer."
    
    elif name == "brave_search":
        try:
            api_key = os.getenv("BRAVE_API_KEY")
            if not api_key:
                return "Error: BRAVE_API_KEY not found in environment variables"
            
            query = args["query"]
            count = args.get("count", 10)
            
            # Brave Search API endpoint
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": api_key
            }
            params = {
                "q": query,
                "count": min(count, 20)  # Max 20 results
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                # Extract web results
                if "web" in data and "results" in data["web"]:
                    for idx, result in enumerate(data["web"]["results"][:count], 1):
                        results.append({
                            "position": idx,
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "description": result.get("description", "")
                        })
                
                if results:
                    formatted_results = "\n\n".join([
                        f"{r['position']}. {r['title']}\n   URL: {r['url']}\n   {r['description']}"
                        for r in results
                    ])
                    return f"Search Results for '{query}':\n\n{formatted_results}"
                else:
                    return f"No results found for query: {query}"
            else:
                return f"Error: Brave API returned status code {response.status_code}\n{response.text}"
        
        except requests.exceptions.Timeout:
            return "Error: Search request timeout"
        except Exception as e:
            return f"Error during search: {str(e)}"
    
    elif name == "ask_question":
        # Terminal tool - ask patient a question
        question = args["question"]
        confidence = args["confidence"]
        reasoning = args.get("reasoning", "")
        
        # Return structured response indicating this terminates the loop
        result = {
            "type": "question",
            "question": question,
            "letter_choice": None,
            "confidence": confidence,
            "usage": {"input_tokens": 0, "output_tokens": 0}
        }
        return result
    
    elif name == "make_choice":
        # Terminal tool - make diagnosis choice
        letter_choice = args["letter_choice"] if args["letter_choice"] else "bad make choice tool call"
        confidence = args["confidence"]
        reasoning = args.get("reasoning", "")
        
        # Return structured response indicating this terminates the loop
        result = {
            "type": "choice",
            "letter_choice": letter_choice,
            "confidence": confidence,
            "usage": {"input_tokens": 0, "output_tokens": 0}
        }
        return result
    
    return "Unknown tool"