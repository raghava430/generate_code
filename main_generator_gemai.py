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
        self.max_retries = 5

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

{"PREVIOUS CODE CONTEXT:" + previous_code if previous_code else ""}


OUTPUT Rules:
- write only executable python code 
- NO markdown, NO ```, NO explanations  
- Start with complete import statements
- Double-check syntax

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

    REQUIREMENTS:
    - Use proper Python import syntax with "import" or "from...import"
    - Include error handling as specified
    - Add brief comments for key logic
    - Ensure code is immediately executable
    - Double-check all import statements follow the correct format above

CODE:"""

    def create_error_fixing_prompt(self, plan_step: Dict, failed_code: str, error_message: str) -> str:
        """Create a prompt to fix code based on error."""
        return f"""You are a Python debugging and testing expert. The following code failed with an error.

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

    def create_test_prompt(self, all_previous_plans: List[Dict], current_plan: Dict, 
                           prev_code: str, current_code: str, imports: List[str]) -> str:
        """
        Create a prompt for generating pytest test code for the current step.
        Combines all previous and current plans/code for context.
        """
        # Combine all plan steps for context
        all_plans_text = "\n".join([
            f"Step {p.get('step_number')}: {p.get('description')} - {p.get('code_purpose')}"
            for p in all_previous_plans
        ])
        all_plans_text += f"\nCurrent Step {current_plan.get('step_number')}: {current_plan.get('description')} - {current_plan.get('code_purpose')}"

        # Combine code
        combined_code = prev_code + "\n\n" + current_code if prev_code else current_code

        # Format imports
        imports_text = "\n".join(imports) if imports else ""

        return f"""You are a senior Python tester and debugger. Generate pytest test code to validate the following feature code.

PLAN CONTEXT (ALL STEPS): what this codde is part of 
{all_plans_text}

CRITICAL INSTRUCTIONS:
- DO NOT use importlib or module imports
- Test the code INLINE (single script, not a module)
- Mock all external dependencies based on context above
- Focus on runtime validation: code executes without exceptions


CODE TO TEST:
{imports_text}

{combined_code}

YOUR TASK:
1. Generate a complete pytest test that validates this code works correctly
2. The test should check for:
   - No runtime errors when code executes
   - Basic functionality works (variables are assigned, no exceptions)
   - Code doesn't have import errors or missing dependencies
3. Use mock data or mock objects where necessary (e.g., mock file paths, mock web elements)
4. Keep test simple and focused on runtime validation, not full integration testing

IMPORTANT REQUIREMENTS:
- Start your response with a list of required libraries in this format:
  REQUIRED_LIBRARIES: pandas, selenium, openpyxl, pytest, pytest-mock
- Then provide the complete pytest code
- Use pytest fixtures and mocking to avoid actual file/web operations
- The test should be runnable with: pytest <filename>
- Include try-except in test to catch any runtime errors

OUTPUT FORMAT:
Line 1: REQUIRED_LIBRARIES: pytest, pytest-mock, [any other libraries needed]
Line 2+: Complete pytest code that copies the above code inline and tests it

Generate the test code now."""

    def dryrun_test(self, all_previous_plans: List[Dict], current_plan: Dict,
                    prev_code: str, current_code: str, imports: List[str]) -> Tuple[bool, str]:
        """
        Generate and execute a pytest test for the combined code.
        Returns (success, error_message)
        """
        print(f"  → Running dry-run test for step {current_plan.get('step_number')}...")

        # Generate test code using LLM
        test_prompt = self.create_test_prompt(all_previous_plans, current_plan, 
                                              prev_code, current_code, imports)
        test_response = self.get_llm_response(test_prompt)

        if not test_response:
            return False, "Failed to generate test code from LLM"

        # Extract required libraries
        required_libs = []
        if "REQUIRED_LIBRARIES:" in test_response:
            lib_line = test_response.split("REQUIRED_LIBRARIES:")[1].split("\n")[0]
            required_libs = [lib.strip() for lib in lib_line.split(",")]

        # Extract test code
        test_code = test_response.strip()
        if "```python" in test_code:
            test_code = test_code.split("```python")[1].split("```")[0]
        elif "```" in test_code:
            test_code = test_code.split("```")[1].split("```")[0]
        test_code = test_code.strip()


        tests_dir = "tests"
        if not os.path.exists(tests_dir):
            os.makedirs(tests_dir)
            print(f"  📁 Created '{tests_dir}' directory")
    
        # Create descriptive filename
        step_num = current_plan.get('step_number', 'unknown')
        step_desc = current_plan.get('description', 'test')
        # Clean description for filename (remove special chars)
        clean_desc = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in step_desc)
        clean_desc = clean_desc.replace(' ', '_').lower()[:50]  # Limit length
    
        test_filename = f"test_step_{step_num}_{clean_desc}.py"
        test_filepath = os.path.join(tests_dir, test_filename)
    
        # Create header with context
        test_file_content = f'''"""
Test for Step {step_num}: {current_plan.get('description', 'N/A')}
Purpose: {current_plan.get('code_purpose', 'N/A')}
Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Required Libraries: {", ".join(required_libs)}
"""

{test_code}
'''
    
        # Save to file
        with open(test_filepath, 'w', encoding='utf-8') as f:
            f.write(test_file_content)
    
        print(f"  💾 Test saved: {test_filepath}")

        # Install required libraries
        print(f"   Installing test dependencies: {', '.join(required_libs)}")
        for lib in required_libs:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", lib],
                    capture_output=True,
                    timeout=30
                )
            except Exception as e:
                print(f"   Warning: Failed to install {lib}: {e}")

        # Write test code to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='_test.py', delete=False) as f:
            f.write(test_code)
            test_file = f.name

        try:
            # Run pytest on the test file
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=15
            )

            # Check if test passed
            if result.returncode == 0:
                print(f"   Dry-run test PASSED")
                return True, ""
            else:
                error_msg = result.stdout + "\n" + result.stderr
                print(f"   Dry-run test FAILED")
                return False, f"Pytest failed:\n{error_msg}"

        except subprocess.TimeoutExpired:
            return False, "Test execution timeout (15 seconds)"
        except Exception as e:
            return False, f"Test execution error: {str(e)}"
        finally:
            # Clean up test file
            try:
                os.unlink(test_file)
            except:
                pass

    def get_llm_response(self, prompt: str) -> str:
        """Get response from Google API with detailed logging."""
        print(f"  Calling API with model: {self.model}")
        print(f"  Prompt length: {len(prompt)} characters")
    
        try:
            response = self.client.generate_content(prompt)
            content = response.text
            print(f"   API call successful, response length: {len(content) if content else 0}")
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
                          previous_code: str = "", all_previous_plans: List[Dict] = None) -> Tuple[bool, str, str]:
        """
        Execute a single plan step with validation and dry-run testing.
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
    
                # Skip actual code (has = or ( or [ but not for imports)
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

            # Step 1: Validate syntax
            is_valid, error_msg = self.validate_code(code, imports)

            if not is_valid:
                retries += 1
                print(f"  Validation failed (attempt {retries}): {error_msg}")
                if retries < self.max_retries:
                    fix_prompt = self.create_error_fixing_prompt(current_step, code, error_msg)
                    fix_response = self.get_llm_response(fix_prompt)
                    if fix_response:
                        try:
                            fix_data = json.loads(fix_response)
                            current_step = fix_data.get("revised_plan", current_step)
                        except:
                            pass
                continue

            # Step 2: Dry-run test (after successful validation)
            print(f"  ✓ Syntax validation passed")
            test_passed, test_error = self.dryrun_test(
                all_previous_plans, 
                current_step, 
                previous_code, 
                code, 
                imports
            )

            if test_passed:
                # Test passed, forward code to next step
                return True, code, ""
            else:
                # Test failed, retry with error feedback
                retries += 1
                print(f"  Dry-run test failed (attempt {retries})")
                if retries < self.max_retries:
                    # Go back to code generation with test error context
                    test_fix_prompt = self.create_error_fixing_prompt(
                        current_step, 
                        code, 
                        f"Dry-run test failed:\n{test_error}"
                    )
                    test_fix_response = self.get_llm_response(test_fix_prompt)

                    if test_fix_response:
                        try:
                            # Try to parse as JSON with revised_plan and corrected_code
                            fix_test_data = json.loads(test_fix_response)
                            current_step = fix_test_data.get("revised plan", current_step)
                            if "corrected_code" in fix_test_data:
                                code = fix_test_data ["corrected_code"]
                        except Exception:
                            # Not json treat as raw code
                            code = test_fix_response.strip()
                            if code.startswith("```"):
                                code = code[9:]
                            if code.startswith("```"):
                                code = code[3:]
                            if code.endswith("```"):
                                code = code[:-3]
                            code = code.strip()
                            # Loop back to start of while with the FIXED code
                    continue
                else:
                    return False, code, f"Failed after {self.max_retries} attempts. Last error: {test_error}"

        return False, code, f"Failed after {self.max_retries} attempts"

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
                print(f"  ✓ Step {i+1} completed and tested successfully")
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
            print("✓ Code generation completed successfully!")
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
- Import necessary modules: from selenium and  Use WebDriverWait for waiting on elements.
generate a single script at last , no modules.
REQUIREMENTS:
1. Read each URL from 'urls.xlsx' file which is in same directory (first column, no headers)
2. For each URLafter opening url:
   - Click 'Attachments' tab and wait for 3 secs for page loading
   - Find all PDF files in span elements
   - Extract and print PDF filenames by iniialize an empty list and populate it while searching.
3. Check only up to 2 iframes if no PDFs found.
4.extract their filenames (text containing ".pdf"), and print the list of PDF filenames to the console. Do not download any files—only print the names.
5. Print summary at the end clearly by mentioning each url and its pdf file names 
Add print statements for key steps, like "Navigated to URL", "Clicked Attachments", "Searching for PDFs".
If no PDFs are found, print "No PDF elements found".


Use proper error handling and WebDriverWait instead of time.sleep().
"""

    # Generate the code
    print("Starting code generation process...\n")
    result = agent.generate_code(user_requirement)

    # Save the result
    if result["success"]:
        with open("generated_script_gemai.py", "w") as f:
            f.write(result["code"])
        print("\n✓ Code generated successfully!")
        print("Saved to: generated_script_gemai.py")
        print("-" * 50)
        print(result["code"])
    else:
        print(f"\n✗ Code generation failed: {result['error']}")
        if result.get("code"):
            print("\nPartial code generated:")
            print("-" * 50)
            print(result["code"])
            with open("generated_script_gemai_partial.py", "w") as f:
                f.write(result["code"])
            print("\nPartial code saved to: generated_script_gemai_partial.py")


if __name__ == "__main__":
    main()
