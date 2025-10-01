import os
import sys
import subprocess
import tempfile
import json
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class CodeGenerationAgent:
    """
    An automated code generation agent that uses LLM to generate Python code
    based on user requirements through a plan-check-execute cycle.
    """
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        """Initialize the agent with OpenAI API key and model."""
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_retries = 3
        
    def create_planning_prompt(self, user_requirement: str) -> str:
        """Create a prompt for the planner to analyze requirements and create a step-by-step plan."""
        return f"""You are a Python code planning expert. Analyze the following requirement and create a detailed step-by-step plan for implementation.

USER REQUIREMENT:
{user_requirement}

Please provide a structured plan with the following format:
1. List all necessary imports
2. Break down the implementation into clear, numbered steps
3. For each step, specify:
   - What needs to be done
   - Expected input/output
   - Any error handling needed

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

{f'PREVIOUS CODE CONTEXT:' if previous_code else ''}
{previous_code if previous_code else ''}

Generate ONLY the Python code for this step. Include:
1. Proper error handling
2. Comments explaining key parts
3. Make sure the code is executable

Return ONLY the Python code, no explanations outside of comments."""
        
    def create_error_fixing_prompt(self, plan_step: Dict, failed_code: str, error_message: str) -> str:
        """Create a prompt to fix code based on error."""
        return f"""You are a Python debugging expert. The following code failed with an error.

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
    "revised_plan": {{ ... }},  // Same structure as original plan step
    "corrected_code": "..." // The fixed Python code
}}"""
    
    def get_llm_response(self, prompt: str) -> str:
        """Get response from OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful Python programming assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
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
                timeout=5
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
                         previous_code: str = "") -> Tuple[bool, str, str]:
        """
        Execute a single plan step with retry logic.
        Returns (success, generated_code, error_message)
        """
        retries = 0
        current_step = plan_step.copy()
        
        while retries < self.max_retries:
            # Generate code for this step
            code_prompt = self.create_code_generation_prompt(current_step, previous_code)
            code_response = self.get_llm_response(code_prompt)
            
            if not code_response:
                return False, "", "Failed to get response from LLM"
            
            # Clean the code response (remove markdown if present)
            code = code_response.strip()
            if code.startswith("```python"):
                code = code[9:]
            if code.startswith("```"):
                code = code[3:]
            if code.endswith("```"):
                code = code[:-3]
            code = code.strip()
            
            # Validate the code
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
        
        # Initialize code accumulator
        full_code = []
        imports = plan.get("imports", [])
        
        # Execute each step in the plan
        for i, step in enumerate(plan["steps"]):
            print(f"\nStep {i+1}: {step.get('description', 'Processing...')}")
            
            # Get previous code context
            previous_code = "\n".join(full_code) if full_code else ""
            
            # Execute the step
            success, code, error = self.execute_plan_step(step, imports, previous_code)
            
            if success:
                full_code.append(code)
                print(f"Step {i+1} completed successfully")
            else:
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
                "plan": plan
            }


def main():
    """
    Main function to demonstrate the code generation agent.
    """

    
    # Initialize the agent
    agent = CodeGenerationAgent(api_key = os.getenv("OPENAI_API_KEY"), model="gpt-4o")
    
    # Your specific use case requirement
    user_requirement = """
Build a Selenium web scraper that reads URLs from an Excel file named 'urls.xlsx' in the same directory, processes each URL to extract PDF filenames, prints them to console, and provides a final summary.

Write ALL code in one continuous try-except-finally block with no function definitions.

THE COMPLETE CODE STRUCTURE:
First write all imports at the top.
Then write one try block containing all the main logic.
Then write one except block to catch errors.
Then write one finally block with driver.quit() if applicable.

IMPORTS NEEDED:
import pandas as pd
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

INSIDE THE TRY BLOCK (write this as continuous code):
1. Get the current directory by assigning current_dir = os.path.dirname(os.path.abspath(__file__))
2. Set xlsx_path to os.path.join(current_dir, 'urls.xlsx')
3. Check if the file exists using os.path.exists(xlsx_path), if not print error and exit
4. Read Excel: df = pd.read_excel(xlsx_path, header=None, usecols=[0])
5. Extract URLs: urls = df.iloc[:, 0].astype(str).str.strip().tolist() (do not assume or use column names like 'URL'; always use index 0 since there are no headers)
6. Initialize counters: total_pdfs = 0, error_count = 0, pdf_filenames_all = []
7. Create Chrome options: add --headless, --no-sandbox, --disable-dev-shm-usage
8. Create driver using ChromeDriverManager
9. Loop through each url in urls:
   a. Validate URL: if not url.startswith('http'), skip and increment error_count, print "Invalid URL: {url}"
   b. Try to driver.get(url), if fails increment error_count and continue
   c. Try to click 'Attachments' using WebDriverWait for By.LINK_TEXT or By.XPATH
   d. time.sleep(3)
   e. Find pdf_elements using By.XPATH for elements containing '.pdf' (e.g., "//a[contains(@href, '.pdf')] | //span[contains(text(), '.pdf')]")
   f. If empty, check up to 2 iframes: find iframes, switch to each, search again, switch back
   g. For each element, get text or href, extract filename if ends with '.pdf', append to local list and print "PDF found for {url}: {filename}"
   h. Add len(local_list) to total_pdfs
   i. If any error in this loop, increment error_count and continue
10. After loop, print summary: f"Total PDFs found: {total_pdfs} | Total errors: {error_count}"

EXCEPT BLOCK:
Print the error using print(f"Unexpected error: {e}")

FINALLY BLOCK:
If driver exists, call driver.quit()

CRITICAL RULES:
- NO def statements anywhere
- One try block wrapping ALL main logic (steps 1-10)
- One except block after try
- One finally block after except
- Handle errors per URL without stopping the script
- All code executes sequentially when script runs
- Stop after printing summary, no downloads
- Ensure all generated code is valid Python syntax (e.g., proper assignments, no invalid characters or missing operators)

"""



    
    # Generate the code
    print("Starting code generation process...\n")
    result = agent.generate_code(user_requirement)
    
    # Save the result
    if result["success"]:
        # Save to file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        save_path = os.path.join(base_dir, "generatedscript.py")
        with open(save_path, "w") as f:
            f.write(result["code"])
    
        print("Code generated successfully!")
        print(f"Saved to {save_path}")
        print("-" * 50)
        print(result["code"])
    else:
        print(f"\n Code generation failed: {result['error']}")
        if result.get("code"):
            print("\nPartial code generated:")
            print("-" * 50)
            print(result["code"])
            
            # Save partial code
            with open("generated_selenium_script_partial.py", "w") as f:
                f.write(result["code"])
            print("\nPartial code saved to: generated_script_partial.py")


if __name__ == "__main__":
    main()