import os
import sys
import subprocess
import tempfile
import json
from typing import Dict, List, Optional, Tuple, TypedDict, Annotated
import google.generativeai as genai
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import operator

load_dotenv()

# Define the state structure
class AgentState(TypedDict):
    user_requirement: str
    plan: Optional[Dict]
    current_step: int
    generated_code: List[str]  # Accumulates code from each step
    imports: List[str]
    error_message: Optional[str]
    errors: Annotated[List[str], operator.add]
    max_retries: int
    current_retries: int
    success: bool
    final_code: Optional[str]
    partial: bool
    current_code: Optional[str]
    current_plan_step : Optional[Dict]
    
class CodeGenerationAgent:
    """
    An automated code generation agent that uses LLM to generate Python code
    based on user requirements through a plan-check-execute cycle.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """Initialize the agent with Google API key and Gemini model."""
        genai.configure(api_key=api_key)
        generation_config = genai.GenerationConfig(temperature = 0.0)
        self.client = genai.GenerativeModel(model, generation_config=generation_config)
        self.model = model
        self.max_retries = 10

    def create_planning_prompt(self, user_requirement: str) -> str:
        """Create a prompt for the planner to analyze requirements and create a step-by-step plan."""
        return f"""You are a Python code planning expert. Analyze the following requirement and create a detailed step-by-step plan for implementation.
        take each user requirement seriously and give plan accordingly, don't assume on your own . give exact plan and description in detail as user requirement states.
        IMPORTANT: Give plan into simpler steps, so that implementation and debugging part would be easy. Try to break the plan into reasonable simpler steps.


**CRITICAL LOOP HANDLING RULE:**
When a step requires iterating through a list/collection:
- DO NOT create separate "Start Loop" and "End Loop" steps
- DO NOT create "conceptual" loop steps
- INSTEAD: Create ONE complete step that includes the entire loop with all its logic
- The step should generate a COMPLETE for loop with a valid body containing all processing logic
- Example: Instead of "Step 5: Start URL loop", use "Step 5: Process each URL (navigate, click, extract PDFs, store results)"

USER REQUIREMENT:
{user_requirement}

Please provide a structured plan with the following format:
1. List all necessary imports
2. Break down the implementation into clear, numbered steps
3. For each step, specify:
   - What needs to be done
   - Expected input/output
   - Any error handling needed

   CRITICAL IMPORT FORMAT:
In your JSON "imports" array, use proper Python syntax:
 CORRECT: "from selenium import webdriver"
 CORRECT: "import openpyxl"
 WRONG: "selenium.webdriver"
 WRONG: "selenium.webdriver.support import X"

Output your plan in this JSON format:
{{
  "imports": ["import1", "import2", ...],
  "steps": [
    {{
      "step_number": 1,
      "description": "Step description",
      "code_purpose": "What this code should do",
      "error_handling": "Any specific error handling"
    }},
    ...
  ],
  "expected_output": "Description of final output"
}}

Be specific and detailed in your planning."""

    def create_code_generation_prompt(self, plan_step: Dict, previous_code: str = "") -> str:
        """Create a prompt for code generation based on a plan step."""
        return f"""You are a Python code generator. Generate Python code for the following step.

STEP DETAILS:
Step Number: {plan_step.get('step_number')}
Description: {plan_step.get('description')}
Purpose: {plan_step.get('code_purpose')}
Error Handling: {plan_step.get('error_handling', 'Standard error handling')}

Do Not Modify the exact Xpath.


IMPORT STATEMENT RULES (MANDATORY):
Every import MUST use one of these EXACT formats:

 CORRECT:
  import pandas as pd
  from selenium import webdriver
  from selenium.webdriver.support import expected_conditions as EC
  import openpyxl

 WRONG (DO NOT USE):
  selenium.webdriver
  pandas
  selenium.webdriver.support import expected_conditions as EC

{"PREVIOUS CODE CONTEXT:" + previous_code if previous_code else ""}


OUTPUT Rules:
- write only executable python code 
- NO markdown, NO ```, NO explanations  
- Start with complete import statements
- Double-check syntax



    REQUIREMENTS:
    - Use proper Python import syntax with "import" or "from...import"
    - Include error handling as specified
    - Add brief comments for key logic
    - Ensure code is immediately executable
    - Double-check all import statements follow the correct format above

CODE:"""

    def create_error_fixing_prompt(self, plan_step: Dict, failed_code: str, error_message: str) -> str:
        """Create a prompt to fix code based on error."""
        # Extract specific line number if it's a syntax error
        line_number = None
        if "line" in error_message.lower():
            import re
            line_match = re.search(r'line (\d+)', error_message, re.IGNORECASE)
            if line_match:
                line_number = line_match.group(1)
    
        line_context = ""
        if line_number:
            line_context = f"\n**CRITICAL: The error is on LINE {line_number}. Focus your fix on that specific line.**\n"
        return f"""You are a Python debugging and testing expert. Fix the following code which  failed with an error.

            **CRITICAL IMPORT FORMAT RULES:**
    In your JSON "imports" list, use ONLY these formats:
    - "import module"
    - "import module as alias"  
    - "from module import item"
    - "from module.submodule import item as alias"

ORIGINAL PLAN STEP:
{json.dumps(plan_step, indent=2)}

FAILED CODE: 
{failed_code}

ERROR MESSAGE:focus on {line_context} and secondary focus on {error_message}

DEBUGGING INSTRUCTIONS:
-Identify the EXACT line causing the error (line {line_number if line_number else 'mentioned in error'})
-If it's an "expected an indented block" error, check if there's an empty try/except/if/for/while/def block
-Ensure EVERY control structure (if, for, while, try, except, def, class) has at least one indented statement
-If you want an empty block, use the pass statement
-Check for missing colons, incorrect indentation, or mismatched brackets
-DO NOT regenerate the entire code - FIX only the problematic section

Please analyze the error and provide:
1. A revised plan step if needed (in same JSON format as original)
2. The corrected code

Output in this format:
{{
  "revised_plan": {{ ... }},
  "corrected_code": "..."
}}"""

    def get_llm_response(self, prompt: str) -> str:
        """Get response from Google API with detailed logging."""
        print(f"  Calling API with model: {self.model}")
        print(f"  Prompt length: {len(prompt)} characters")

        #counting tokens before sending to track usage
        token_count = self.client.count_tokens(prompt)
        print(f"Input tokens: {token_count.total_tokens}")  #estimated tokens in prompt before making api call
    
        try:
            response = self.client.generate_content(prompt)
            content = response.text
            #get token usage from response
            print(f"Token Usage:")
            print(f"-- Prompt tokens: {response.usage_metadata.prompt_token_count}") #actual tokens sent as prompt to model
            print(f" -- Completion Tokens: {response.usage_metadata.candidates_token_count}") #tokens in model's generated output
            print(f" -- Total Tokens: {response.usage_metadata.total_token_count}")  # sum of prompt tokens and output tokens
            print(f"   API call successful, response length: {len(content) if content else 0}") # gives length of characters in content
            return content
        
        except Exception as e:
            print("\n" + "!"*60)
            print("CRITICAL ERROR: Google API Call Failed!")
            print(f"  Model: {self.model}")
            print(f"  Error Type: {type(e).__name__}")
            print(f"  Error Message: {str(e)}")
            print("  This is likely due to an invalid API key, network issue, or safety settings.")
            print("!"*60 + "\n")
            return None

    def parse_plan(self, plan_response: str) -> Dict:
        """Parse the planning response to extract structured plan."""
        try:
            # Try to find JSON in the response
            import re
            json_match = re.search(r'\{.*\}', plan_response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback: try to parse the entire response
                return json.loads(plan_response)
        except json.JSONDecodeError:
            print("Failed to parse plan as JSON. Using fallback structure.")
            # Create a basic plan structure as fallback
            return {
                "imports": [],
                "steps": [
                    {
                        "step_number": 1,
                        "description": "Execute the requirement",
                        "code_purpose": plan_response,
                        "error_handling": "Standard error handling"
                    }
                ],
                "expected_output": "As specified in requirements"
            }

    def validate_code(self, code: str, imports: List[str]) -> Tuple[bool, str]:
        """
        Validate generated code by attempting to execute it.
        Returns (success, error_message)
        """
        # Create a complete script with imports
        full_script = "\n".join(imports) + "\n\n" + code

        # Add a main block if not present
        if "if __name__" not in full_script:
            full_script += "\n\nif __name__ == '__main__':\n    pass  # Code validation"

        # Write to temporary file and try to execute
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(full_script)
            temp_file = f.name

        try:
            # Try to compile first
            compile(full_script, temp_file, 'exec')

            # Then try to run with syntax check
            result = subprocess.run(
                [sys.executable, '-m', 'py_compile', temp_file],
                capture_output=True,
                text=True,
                timeout=25
            )

            if result.returncode == 0:
                return True, "Code validated successfully"
            else:
                return False, result.stderr or result.stdout
        except SyntaxError as e:
            return False, f"Syntax Error: {str(e)}"
        except Exception as e:
            return False, f"Validation Error: {str(e)}"
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except:
                pass

    def fix_import_statements(self, code: str) -> str:
        """Fix corrupted import statements in code."""
        # COMPREHENSIVE FIX: Handle all import corruption patterns
        lines = code.split("\n")
        fixed_lines = []
        for line in lines:
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                fixed_lines.append(line)
                continue

            # Skip already correct imports, comments, and code statements
            if stripped.startswith(("#", "import ", "from ", "def ", "class ", "if ", "for ", 
                      "while ", "try:", "except", "return", "print", "@", "async ", "with ")):
                fixed_lines.append(line)
                continue

            # Skip actual code (has =, (, or [ but not for imports)
            if ("=" in stripped or "(" in stripped or "[" in stripped) and " import " not in stripped:
                fixed_lines.append(line)
                continue

            # Fix Pattern 1: "selenium.webdriver.support import expected_conditions as EC"
            # → "from selenium.webdriver.support import expected_conditions as EC"
            if " import " in stripped:
                fixed_lines.append("from " + stripped)                   

            # Fix Pattern 2: "pandas as pd" → "import pandas as pd"
            elif " as " in stripped:
                fixed_lines.append("import " + stripped)                   

            # Fix Pattern 3: "selenium.webdriver.chrome.options" → "import selenium.webdriver.chrome.options"
            elif "." in stripped:
                fixed_lines.append("import " + stripped)                   

            # Fix Pattern 4: Just "os" or "openpyxl" → "import os"
            elif stripped.replace("_", "").replace("-", "").isalnum():
                fixed_lines.append("import " + stripped)

            else:
            # Keep line unchanged if it doesn't match any pattern
                fixed_lines.append(line)

        return "\n".join(fixed_lines)


# Initialize the agent globally
api_key = os.getenv("GOOGLE_API_KEY")
agent = CodeGenerationAgent(api_key=api_key, model="gemini-2.5-flash")

# Define node functions
def planner_node(state: AgentState) -> AgentState:
    """Plan the code generation steps."""
    print("Step 1: Creating execution plan...")
    
    planning_prompt = agent.create_planning_prompt(state["user_requirement"])
    plan_response = agent.get_llm_response(planning_prompt)
    
    if not plan_response:
        state["success"] = False
        state["error_message"] = "Failed to create execution plan"
        return state
    
    plan = agent.parse_plan(plan_response)
    
    print(f"Plan created with {len(plan['steps'])} steps")
    print("\n" + "="*70)
    print("EXECUTION PLAN")
    print("="*70)

    # Display imports
    if plan.get('imports'):
        print("\n Required Imports:")
        for imp in plan['imports']:
            print(f"   • {imp}")

    # Display each step
    print(f"\n Steps ({len(plan['steps'])} total):")
    print("-"*70)

    for i, step in enumerate(plan['steps'], 1):
        print(f"\nStep {i}: {step.get('description', 'N/A')}")
        print(f"   Purpose: {step.get('code_purpose', 'N/A')}")
        if step.get('error_handling'):
            print(f"   Error Handling: {step.get('error_handling')}")

    print("-"*70)
    print(f" Expected Output: {plan.get('expected_output', 'As specified')}")
    print("="*70 + "\n")
    
    state["plan"] = plan
    state["imports"] = plan.get("imports", [])
    state["current_step"] = 0
    state["generated_code"] = []
    state["current_retries"] = 0
    
    return state

def code_generator_node(state: AgentState) -> AgentState:
    """Generate code for current step."""
    plan = state["plan"]
    current_step_idx = state["current_step"]
    
    if current_step_idx >= len(plan["steps"]):
        # All steps completed
        state["success"] = True
        return state
    
    step = plan["steps"][current_step_idx]
    print(f"\nStep {current_step_idx + 1}: {step.get('description', 'Processing...')}")
    
    # Get previous code context
    previous_code = "\n".join(state["generated_code"]) if state["generated_code"] else ""
    
    # Generate code for this step
    code_prompt = agent.create_code_generation_prompt(step, previous_code)
    code_response = agent.get_llm_response(code_prompt)
    
    if not code_response:
        state["error_message"] = "Failed to get response from LLM"
        state["success"] = False
        return state
    
    # Clean the code response
    code = code_response.strip()
    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    code = code.strip()
    
    # Fix import statements
    code = agent.fix_import_statements(code)
    
    # Store the generated code temporarily for validation
    state["current_code"] = code
    state["current_plan_step"] = step
    
    return state

def validator_node(state: AgentState) -> AgentState:
    """Validate the generated code."""
    code = state.get("current_code", "")
    imports = state["imports"]
    
    is_valid, error_msg = agent.validate_code(code, imports)
    
    if is_valid:
        state["error_message"] = None
        state["current_retries"] = 0  # Reset retries on success
        return state
    else:
        state["error_message"] = error_msg
        state["current_retries"] += 1
        #accumulate errors to error list
        current_step_num = state["current_step"] +1
        line_info = ""
        if "line" in error_msg.lower():
            line_info = f" (check specific line mentioned in the error)"
        error_entry = f"Step {current_step_num} Attempt {state['current_retries']}: {error_msg}{line_info}"
        state["errors"] = [error_entry]
        print(f"Attempt {state['current_retries']} failed. Error: {error_msg}")

        return state

def code_fixer_node(state: AgentState) -> AgentState:
    """Fix the code based on error."""
    current_step_num = state["current_step"] +1

    # Add error to accumulated errors list
    error_entry = f"Step {current_step_num}, Attempt {state['current_retries']}: {state.get('error_message', 'Unknown error')}"
    state["errors"] = [error_entry]

    if state["current_retries"] >= state["max_retries"]:
        print(f" Max Retries: {state['max_retries']} reached for step {current_step_num}")
        return state
    
    step = state.get("current_plan_step")
    code = state.get("current_code", "")
    error = state.get("error_message", "")
    
    fix_prompt = agent.create_error_fixing_prompt(step, code, error)
    fix_response = agent.get_llm_response(fix_prompt)
    
    if fix_response:
        try:
            fix_data = json.loads(fix_response)
            # Update the plan step if revised
            if "revised_plan" in fix_data:
                state["current_plan_step"] = fix_data["revised_plan"]
            # Get the corrected code
            if "corrected_code" in fix_data:
                code = fix_data["corrected_code"]
                # Clean and fix the corrected code
                if code.startswith("```python"):
                    code = code[9:]
                if code.startswith("```"):
                    code = code[3:]
                if code.endswith("```"):
                    code = code[:-3]
                code = code.strip()
                code = agent.fix_import_statements(code)
                state["current_code"] = code
        except:
            # If parsing fails, continue with original code
            pass
    
    return state

def step_success_node(state: AgentState) -> AgentState:
    """Handle successful step completion."""
    # Add the validated code to generated_code list
    state["generated_code"].append(state.get("current_code", ""))
    print(f" Step {state['current_step'] + 1} completed.")
    
    # Move to next step
    state["current_step"] += 1
    state["current_retries"] = 0
    
    # Check if there are more steps
    if state["current_step"] >= len(state["plan"]["steps"]):
        state["success"] = True
    
    return state
    
def step_failure_node(state: AgentState) -> AgentState:
    """Handle step failure after retries exhausted - save failed node"""
    failed_code = state.get("current_code", "")
    current_step_num = state["current_step"] +1

    print (f" Step :{current_step_num} failed after {state['max_retries']} retries")
    print (f" Saving Failed code to 'failed_script.py'...")

    #save failed code to a seperate file
    if failed_code:
        try:
            with open("failed_script.py", "w") as f:
                #Include imports and all accumulated code + failed code
                full_failed = "\n\n".join(state["imports"]) +"\n\n"
                full_failed += "\n\n".join(state["generated_code"]) +"\n\n"
                full_failed += f"# FAILED CODE FROM STEP {current_step_num}\n"
                full_failed += failed_code
                f.write(full_failed)
            print("Failed code saved to 'failed_script.py'")
        except Exception as e:
            print (f"Error saving failed code: {e}")

    # Add failed code to genrated_code for partial save
    error_summary = f"Step {current_step_num} FAILED after {state['max_retries']} attempts. Last Error: {state.get('error_message','Unknown')}"
    state["errors"] = [error_summary]

    state["success"] = False
    state["partial"] = True

    return state


def finalizer_node(state: AgentState) -> AgentState:
    """Finalize and combine all code."""
    imports = state["imports"]
    generated_code = state["generated_code"]
    
    # Combine all code
    final_code = "\n\n".join(imports) + "\n\n" + "\n\n".join(generated_code)
    state["final_code"] = final_code
    
    print("\nCode generation process completed.")
    return state

def final_validator_node(state: AgentState) -> AgentState:
    """Final validation of complete code."""
    print("\nPerforming final validation...")
    
    generated_code = state["generated_code"]
    imports = state["imports"]
    
    # Validate the complete code
    is_valid, error_msg = agent.validate_code("\n\n".join(generated_code), imports)
    
    if is_valid:
        print("Code generation completed successfully!")
        state["success"] = True
        state["error_message"] = None
    else:
        state["success"] = False
        state["error_message"] = f"Final validation failed: {error_msg}"
        state["partial"] = True
    
    # Handle saving partial code if needed
    if state.get("partial") and state.get("final_code"):
        with open("generated_script_gemai_partial.py", "w") as f:
            f.write(state["final_code"])
        print("\nPartial code saved to: generated_script_gemai_partial.py")
    
    return state

# Define conditional edges
def should_fix_code(state: AgentState) -> str:
    """Determine if code needs fixing after validation."""
    if state.get("error_message") and state["current_retries"] < state["max_retries"]:
        return "fix"
    elif state.get("error_message") and state["current_retries"] >= state["max_retries"]:
        return "fail"
    else:
        return "success"

def should_continue_or_finalize(state: AgentState) -> str:
    """Determine if should continue to next step or finalize."""
    if state["current_step"] < len(state["plan"]["steps"]):
        return "continue"
    else:
        return "finalize"

# Build the graph
def create_workflow():
    """Create the LangGraph workflow."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("code_generator", code_generator_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("code_fixer", code_fixer_node)
    workflow.add_node("step_success", step_success_node)
    workflow.add_node("step_failure", step_failure_node)
    workflow.add_node("finalizer", finalizer_node)
    workflow.add_node("final_validator", final_validator_node)
    
    # Add edges
    workflow.add_edge("planner", "code_generator")
    workflow.add_edge("code_generator", "validator")
    workflow.add_edge("code_fixer", "validator")           # Edge from code_fixer back to validator
    workflow.add_edge("step_failure", END)
    workflow.add_edge("finalizer", "final_validator")  # Edge from finalizer to final validator
    workflow.add_edge("final_validator", END)         # Final validator to END
    
    
    # Conditional edge from validator
    workflow.add_conditional_edges(
        "validator",
        should_fix_code,
        {
            "fix": "code_fixer",
            "success": "step_success",
            "fail": "step_failure"  # If max retries reached, go to finalizer
        }
    )
    

    
    # Conditional edge from step_success
    workflow.add_conditional_edges(
        "step_success",
        should_continue_or_finalize,
        {
            "continue": "code_generator",
            "finalize": "finalizer"
        }
    )
    
    # Set entry point
    workflow.set_entry_point("planner")
    
    return workflow

def main():
    """Main function to demonstrate the code generation agent."""
    print("=" * 60)
    print("Diagnostic checks")
    print("=" * 60)

    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        print(f"API Key loaded: {api_key[:8]}...{api_key[-4:]}")
    else:
        print("ERROR: GOOGLE_API_KEY not found in environment")
        print("Make sure .env file exists with: GOOGLE_API_KEY=your-key")
        return
    
    # Check 2: Model name
    model = "gemini-2.5-flash"
    print(f" Model: {model}")
    
    # Check 3: Google AI library version
    import google.generativeai as genai
    print(f" Google AI library version: {genai.__version__}")
    
    print("=" * 60)
    print()
    
    # Your specific use case requirement
    user_requirement = """
Build a Selenium web scraper that reads URLs from an Excel file and extracts PDF filenames.Given a target URL which is in urls.xlsx in same directory like "https://services.seattle.gov/portal/customize/LinkToRecord.aspx?altId=3003279-EX",
 navigate to the URL,  
Use Selenium with Chrome in headless mode.
- Import necessary modules: from selenium and  IMPORTANT: Use WebDriverWait for waiting on elements.
generate a single script at last , no modules.
REQUIREMENTS:
1. Read urls from 'urls.xlsx' file IMPORTANT: the urls.xlsx file is in same directory from where we are running the code. (read from first column, there are no headers) and store them in a list.
2. Create an empty dictionary to store results for all urls.
3. process each url one by one from list:
    - navigate to current url
   - Click 'Attachments' tab and wait for 5 secs for page loading.(For locating the 'Attachments' tab, you MUST use the locator (By.PARTIAL_LINK_TEXT, 'Attachments'). Do not use any other XPath or CSS selector for this element.)
   - wait for iframe to be present. after switching to iframe, use this approach-
   - Wait up to 10 seconds and Search for PDF filenames inside iframes using this EXACT XPath (DO NOT MODIFY):
   .//span[contains(translate(text(),'PDF','pdf'), '.pdf')] 
    ***CRITICAL: Must use <span> elements, NOT <a> elements!Extract the TEXT content from span elements, not href attributes.***
   - For each element found, extract text and check if it contains '.pdf'
   (case-insensitive). If yes, store the url and its found pdfs in results dictionary. 
   - print intermediate results for current url.
3. Check only up to 2 iframes if no PDFs found.
4. Do not download any files—only print the names. and close the webdriver at end.
5. Print summary at the end clearly by mentioning each url and its pdf file names 
Add print statements for key steps, similar to like "Navigated to URL", "Clicked Attachments", "Searching for PDFs".
If no PDFs are found, print "No PDF elements found".

make each step independent , don't have step by step nested structures, avoid loops that span multiple steps
Use proper error handling and strictly use WebDriverWait instead of time.sleep().
"""
    
    # Create initial state
    initial_state = {
        "user_requirement": user_requirement,
        "plan": None,
        "current_step": 0,
        "generated_code": [],
        "imports": [],
        "error_message": None,
        "errors": [],
        "max_retries": 10,
        "current_retries": 0,
        "success": False,
        "final_code": None,
        "partial": False,
        "current_code": None,
        "current_plan_step": None
    }
    
    # Create and compile the workflow
    print("Starting code generation process...\n")
    workflow = create_workflow()
    
    # Create memory for checkpointing
    memory = MemorySaver()
    
    # Compile the graph
    app = workflow.compile(checkpointer=memory)
    
    # Run the workflow
    config = {"configurable": {"thread_id": "code_generation_1"},
              "recursion_limit" : 100
              }
    final_state = app.invoke(initial_state, config)
    
    # Handle the results
    if final_state["success"]:
        with open("generated_script_gemai.py", "w") as f:
            f.write(final_state["final_code"])
        print("\n Code generated successfully!")
        print("Saved to: generated_script_gemai.py")
        print("-" * 50)
        print(final_state["final_code"])
    else:
        print(f"\n Code generation failed: {final_state.get('error_message', 'Unknown error')}")
        if final_state.get("final_code"):
            print("\nPartial code generated:")
            print("-" * 50)
            print(final_state["final_code"])

if __name__ == "__main__":
    main()