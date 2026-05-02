# Agentic Code Generator with Gemini and LangGraph

An agentic Python code-generation framework that uses Google Gemini and LangGraph to generate Python automation scripts from natural-language requirements.

This project is designed around a practical scraping workflow: it can generate code for reading website URLs from an Excel file, visiting those websites, scraping attachment sections, identifying PDF files, and producing/downloading PDF-related outputs depending on the user requirement.

The agent follows a plan-generate-validate-fix workflow:

- Creates an implementation plan from a user requirement
- Generates Python code step by step
- Validates generated code for syntax errors
- Retries and fixes failed steps
- Saves the final generated script or partial output when errors occur

## Features

- Gemini-powered planning and code generation
- LangGraph workflow orchestration
- Step-by-step Python code generation
- Syntax validation using Python compilation
- Retry and repair loop for failed code
- Partial output saving for debugging
- Environment-based API key configuration
- Supports scraper-generation workflows using Excel-based URL input

## Example Use Case

The current example focuses on generating a Selenium-based website scraper/downloader workflow.

The generated script can be customized to:

- Read URLs from an Excel file such as `urls.xlsx`
- Open each website URL in a browser automation session
- Navigate to attachment or document sections
- Search for PDF files on the page or inside iframes
- Extract PDF filenames or links
- Download PDFs when the requirement asks for downloading
- Print a clear summary of processed URLs and discovered PDF files

## Project Structure

```text
.
├── agentic_code_generator.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Requirements

- Python 3.10+
- Google Gemini API key

## Installation

Clone the repository:

```bash
git clone https://github.com/raghava430/generate_code.git
cd generate_code
```

Create and activate a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Setup

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_google_api_key_here
```

Do not commit `.env` to GitHub.

## Usage

Run the agent:

```bash
python agentic_code_generator.py
```

The script reads the `user_requirement` defined inside the `main()` function, creates a step-by-step plan, generates Python code through the LangGraph workflow, validates each step, and saves the generated output.

To customize the generated scraper/downloader, update the `user_requirement` variable with details such as:

```text
Build a Selenium scraper that reads URLs from urls.xlsx, opens each URL, finds PDF attachments, downloads the PDF files, and prints a summary for each website.
```

## Tech Stack

- Python
- Google Gemini
- LangGraph
- python-dotenv
- Selenium-oriented generated workflows
- Excel-based input workflows

## Notes

Generated scripts, failed scripts, local Excel files, downloaded PDFs, virtual environments, cache files, and environment variables should not be committed to GitHub.

Sensitive values such as API keys must stay in `.env`, which is ignored by Git.

## License

This project is for portfolio and learning purposes.
