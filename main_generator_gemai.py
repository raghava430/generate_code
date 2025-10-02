import os
import sys
import subprocess
import tempfile
import json
from typing import Dict, List, Optional, Tuple
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class CodeGenerationAgent:
    """
    An automated code generation agent that uses LLM to generate Python code
    based on user requirements through a plan-check-execute cycle.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """Initialize the agent with Google API key and Gemini model."""
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)
        self.model = model
        self.max_retries = 15

    def create_planning_prompt(self, user_requirement: str) -> str:
        """Create a prompt for the planner to analyze requirements and create a step-by-step plan."""
        return f"""You are a Python code planning expert. Analyze the following requirement and create a detailed step-by-step plan for implementation.
        take each user requirement seriously and give plan accordingly, don't assume on your own . give exact plan and description in detail as user requirement states.
        IMPORTANT: Give plan into simpler steps, so that implementation and debugging part would be easy. Try to break the plan into reasonable simpler steps.

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

ERROR MESSAGE:
{error_message}

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

    def execute_plan_step(self, plan_step: Dict, imports: List[str],
                          previous_code: str = "", all_previous_plans: List[Dict] = None) -> Tuple[bool, str, str]:
        """
        Execute a single plan step with validation.
        Returns (success, generated_code, error_message)
        """
        if all_previous_plans is None:
            all_previous_plans = []

        retries = 0
        current_step = plan_step.copy()

        while retries < self.max_retries:
            # Generate code for this step
            code_prompt = self.create_code_generation_prompt(current_step, previous_code)
            code_response = self.get_llm_response(code_prompt)

            if not code_response:
                return False, "", "Failed to get response from LLM"

            # Clean the code response
            code = code_response.strip()
            if code.startswith("```python"):
                code = code[9:]
            if code.startswith("```"):
                code = code[3:]
            if code.endswith("```"):
                code = code[:-3]
            code = code.strip()

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

            code = "\n".join(fixed_lines)
            

            # Validate syntax
            is_valid, error_msg = self.validate_code(code, imports)

            if is_valid:
                return True, code, ""
            
            # If validation failed, try to fix
            retries += 1
            print(f"Attempt {retries} failed. Error: {error_msg}")
            
            if retries < self.max_retries:
                # Get fix from planner
                fix_prompt = self.create_error_fixing_prompt(current_step, code, error_msg)
                fix_response = self.get_llm_response(fix_prompt)
                
                if fix_response:
                    try:
                        # Parse the fix response
                        fix_data = json.loads(fix_response)
                        current_step = fix_data.get("revised_plan", current_step)
                        # The next iteration will use the revised plan
                    except:
                        # If parsing fails, continue with original plan
                        pass
        
        return False, code, f"Failed after {self.max_retries} attempts. Last error: {error_msg}"
                

    def generate_code(self, user_requirement: str) -> Dict:
        """
        Main method to generate code from user requirements.
        Returns a dictionary with success status, generated code, and any errors.
        """
        print("Step 1: Creating execution plan...")

        # Get plan from LLM
        planning_prompt = self.create_planning_prompt(user_requirement)
        plan_response = self.get_llm_response(planning_prompt)

        if not plan_response:
            return {
                "success": False,
                "code": "",
                "error": "Failed to create execution plan"
            }

        # Parse the plan
        plan = self.parse_plan(plan_response)

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

        # Initialize code accumulator
        full_code = []
        imports = plan.get("imports", [])
        all_previous_plans = []

        # Execute each step in the plan
        for i, step in enumerate(plan["steps"]):
            print(f"\nStep {i+1}: {step.get('description', 'Processing...')}")

            # Get previous code context
            previous_code = "\n".join(full_code) if full_code else ""

            # Execute the step with plan history
            success, code, error = self.execute_plan_step(
                step, 
                imports, 
                previous_code,
                all_previous_plans
            )

            if success:
                full_code.append(code)
                all_previous_plans.append(step)
                print(f" Step {i+1} completed.")
            else:
                print(f"\n❌ Step {i+1} FAILED")
                print("="*70)
                print("Failed Code:")
                print("-"*70)
                print(code)
                print("-"*70) 
                print(f"Error: {error}\n")
                return {
                    "success": False,
                    "code": "\n".join(imports) + "\n\n" + "\n".join(full_code),
                    "error": f"Failed at step {i+1}: {error}",
                    "partial": True
                }

        # Combine all code
        final_code = "\n".join(imports) + "\n\n" + "\n\n".join(full_code)

        # Final validation
        print("\nPerforming final validation...")
        is_valid, error_msg = self.validate_code("\n\n".join(full_code), imports)

        if is_valid:
            print("Code generation completed successfully!")
            return {
                "success": True,
                "code": final_code,
                "error": None,
                "plan": plan
            }
        else:
            return {
                "success": False,
                "code": final_code,
                "error": f"Final validation failed: {error_msg}",
                "plan": plan,
                "partial": True
            }


def main():
    """
    Main function to demonstrate the code generation agent.
    """
    print("=" * 60)
    print("Diagnostic checks")
    print("=" * 60)

    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        print (f"API Key loaded: {api_key[:8]}...{api_key[-4:]}")
    else:
        print("ERROR: GOOGLE_API_KEY not found in environment")
        print("Make sure .env file exists with: GOOGLE_API_KEY=sk-...")
        return
    # Check 2: Model name
    model = "gemini-2.5-flash"
    print(f" Model: {model}")
    
    # Check 3: Google AI library version
    import google.generativeai as genai
    print(f" Google AI library version: {genai.__version__}")
    
    print("=" * 60)
    print()

    
    # Initialize the agent
    agent = CodeGenerationAgent(api_key=api_key, model=model)

    # Your specific use case requirement
    user_requirement = """
Build a Selenium web scraper that reads URLs from an Excel file and extracts PDF filenames.Given a target URL which is in urls.xlsx in same directory like "https://services.seattle.gov/portal/customize/LinkToRecord.aspx?altId=3003279-EX",
 navigate to the URL,  
Use Selenium with Chrome in headless mode.
- Import necessary modules: from selenium and  IMPORTANT: Use WebDriverWait for waiting on elements.
generate a single script at last , no modules.
REQUIREMENTS:
1. Read each URL one by one from 'urls.xlsx' file IMPORTANT: the urls.xlsx file is in same directory from where we are running the code. (read from first column, there are no headers)
2. For each URLafter opening url one by one:
   - Click 'Attachments' tab and wait for 5 secs for page loading.(for finding attachments tab use this structure  (By.LINK_TEXT, "Attachments") )
   - wait for iframe to be present. after switching to iframe, use this approach-
   - Wait up to 10 seconds for spans using XPath:
   "//span[contains(translate(text(),'PDF','pdf'), '.pdf')]"
   - For each element found, extract text and check if it contains '.pdf'
   (case-insensitive). If yes, add to PDF list.by iniialize an empty list and populate it while searching.
3. Check only up to 2 iframes if no PDFs found.
4. Do not download any files—only print the names.
5. Print summary at the end clearly by mentioning each url and its pdf file names 
Add print statements for key steps, similar to like "Navigated to URL", "Clicked Attachments", "Searching for PDFs".
If no PDFs are found, print "No PDF elements found".


Use proper error handling and strictly use WebDriverWait instead of time.sleep().
"""

    # Generate the code
    print("Starting code generation process...\n")
    result = agent.generate_code(user_requirement)

    # Save the result
    if result["success"]:
        with open("generated_script_gemai.py", "w") as f:
            f.write(result["code"])
        print("\n Code generated successfully!")
        print("Saved to: generated_script_gemai.py")
        print("-" * 50)
        print(result["code"])
    else:
        print(f"\n Code generation failed: {result['error']}")
        code_content = result.get("code", "").strip()
        has_meaningful_code = len(code_content) > 10
        if has_meaningful_code or result.get("partial"):
            print("\nPartial code generated:")
            print("-" * 50)

            plan_imports = result.get("plan", {}).get("imports", [])
            partial_code = result.get("code", "")
            # Combine imports and code
            if plan_imports:
                partial_output = "\n".join(plan_imports) + "\n\n" + partial_code
            else:
                partial_output = partial_code
    
            print(partial_output)
            with open("generated_script_gemai_partial.py", "w") as f:
                f.write(partial_output)
            print("\nPartial code saved to: generated_script_gemai_partial.py")


if __name__ == "__main__":
    main()
