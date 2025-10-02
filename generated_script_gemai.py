from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import openpyxl
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
import sys

# Initialize driver variable to None, to ensure it's defined even if an error occurs
driver = None

# Configure Chrome options for headless mode
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run Chrome in headless mode (no GUI)
chrome_options.add_argument("--disable-gpu")  # Recommended for headless on some systems
chrome_options.add_argument("--window-size=1920x1080")  # Set a consistent window size
chrome_options.add_argument("--no-sandbox") # Bypass OS security model, sometimes needed in specific environments (e.g., Docker)
chrome_options.add_argument("--disable-dev-shm-usage") # Overcomes limited resource problems in some environments

# Initialize WebDriver with error handling
try:
    # Attempt to start the Chrome WebDriver with configured options
    driver = webdriver.Chrome(options=chrome_options)
except WebDriverException as e:
    # Catch exceptions if the WebDriver fails to initialize
    print(f"Error: WebDriver failed to initialize. Please ensure Chrome browser and ChromeDriver are installed and compatible.")
    print(f"Details: {e}")
    sys.exit(1) # Exit the script if WebDriver initialization fails

# Define the Excel filename constant
EXCEL_FILENAME = 'urls.xlsx'

# Initialize an empty dictionary to store results for each URL
all_results = {}

import openpyxl
import sys

# Initialize an empty list to store URLs
url_list = []

try:
    # Load the workbook from the specified filename
    workbook = openpyxl.load_workbook(EXCEL_FILENAME)
    # Select the active sheet
    sheet = workbook.active

    # Iterate through rows in the sheet
    for row in sheet.iter_rows():
        # Get the cell object from the first column (index 0) of the current row
        cell = row[0]

        # Check if the cell has a value before appending to the list
        if cell.value:
            # Convert the cell value to a string, strip leading/trailing whitespace, and add to the list
            url_list.append(str(cell.value).strip())

except FileNotFoundError:
    # Handle the case where 'urls.xlsx' does not exist
    print(f"Error: The file '{EXCEL_FILENAME}' was not found in the current directory.")
    sys.exit(1) # Exit the script with an error code

except openpyxl.utils.exceptions.InvalidFileException:
    # Handle the case where 'urls.xlsx' is corrupted or not a valid Excel file
    print(f"Error: The file '{EXCEL_FILENAME}' is corrupted or not a valid Excel file.")
    sys.exit(1) # Exit the script with an error code

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

# Main loop to process each URL
for current_url in url_list:
    print(f"\nProcessing URL: {current_url}")
    try:
        # Navigate to the URL
        driver.get(current_url)

        # Wait for the page to load (you might need to adjust the condition)
        # Example: wait until the body element is present
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2) # Give some extra time for dynamic content to load

        # --- Placeholder for finding attachments (e.g., specific links) ---
        # This part would typically involve more specific logic based on the website's structure.
        # For now, let's just log a placeholder message.
        print(f"  Attempting to find attachments on {current_url}...")
        found_attachments = []
        try:
            # Example: Find all <a> tags (links) that might represent attachments
            # This is a very general approach; specific sites will need targeted selectors
            links = driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                href = link.get_attribute("href")
                if href and ("download" in href or ".zip" in href or ".rar" in href or ".tar" in href): # Simplified check
                    found_attachments.append(href)
            if found_attachments:
                print(f"  Found potential attachments: {len(found_attachments)} items.")
            else:
                print("  No obvious attachments found based on a general link search.")
        except Exception as e:
            print(f"  Error finding attachments on {current_url}: {e}")

        # --- Placeholder for searching for PDFs ---
        print(f"  Searching for PDFs on {current_url}...")
        found_pdfs = []
        try:
            # Example: Find all <a> tags with href ending in .pdf
            pdf_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf')]")
            for pdf_link in pdf_links:
                pdf_url = pdf_link.get_attribute("href")
                if pdf_url:
                    found_pdfs.append(pdf_url)
            if found_pdfs:
                print(f"  Found PDFs: {len(found_pdfs)} items.")
            else:
                print("  No PDF links found.")
        except Exception as e:
            print(f"  Error searching for PDFs on {current_url}: {e}")


        # Store results for the current URL
        all_results[current_url] = {
            'attachments': found_attachments,
            'pdfs': found_pdfs,
            'status': 'Processed Successfully'
        }

    except TimeoutException:
        print(f"  Error: Timeout while loading page for {current_url}. Skipping.")
        all_results[current_url] = {'status': 'Timeout Error'}
    except NoSuchElementException as e:
        print(f"  Error: Element not found on {current_url}. Details: {e}. Skipping.")
        all_results[current_url] = {'status': f'Element Not Found Error: {e}'}
    except StaleElementReferenceException:
        print(f"  Error: Stale element encountered on {current_url}. Page might have changed dynamically. Skipping.")
        all_results[current_url] = {'status': 'Stale Element Error'}
    except WebDriverException as e:
        print(f"  Error: A WebDriver-related issue occurred for {current_url}. Details: {e}. Skipping.")
        all_results[current_url] = {'status': f'WebDriver Error: {e}'}
    except Exception as e:
        # Catch any other unexpected errors and continue processing
        print(f"  An unexpected error occurred while processing {current_url}: {e}")
        all_results[current_url] = {'status': f'Unexpected Error: {e}'}

# Note: The 'driver.quit()' and further processing of 'all_results' would typically follow this loop.

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Assuming 'driver', 'url_list', and 'all_results' are initialized from previous steps.

# Main loop to process each URL (context from previous step)
for current_url in url_list:
    print(f"\nProcessing URL: {current_url}")

    try:
        # Navigate to the current URL
        driver.get(current_url)

        # Wait for the page to load, ensuring the body element is present within 30 seconds
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        print(f"Navigated to URL: {current_url}") # Log successful navigation

    except TimeoutException as e:
        # Handle cases where the page takes too long to load or the element is not found
        print(f"Failed to navigate to {current_url}: Timeout Exception - {e}")
        all_results[current_url] = {'status': 'Navigation Timeout Error'}
        continue # Skip to the next URL if navigation fails

    except WebDriverException as e:
        # Catch other WebDriver-related issues during navigation (e.g., browser crash, connection error)
        print(f"Failed to navigate to {current_url}: WebDriver Exception - {e}")
        all_results[current_url] = {'status': f'Navigation WebDriver Error: {e}'}
        continue # Skip to the next URL if navigation fails

    except Exception as e:
        # Catch any other unexpected errors during the navigation process
        print(f"Failed to navigate to {current_url}: Unexpected Error - {e}")
        all_results[current_url] = {'status': f'Navigation Unexpected Error: {e}'}
        continue # Skip to the next URL if navigation fails

    # --- The code for finding attachments, PDFs, and other scraping actions
    #     would follow here, only executing if navigation was successful.
    #     The original 'time.sleep(2)' can be re-added here if additional
    #     settling time is needed for dynamic content after page load.
    
    # Placeholder for the rest of the scraping logic from the previous context:
    # For now, we'll just show where it would fit after successful navigation.
    # The rest of the original try-except block in the context should be adjusted
    # to handle exceptions for these subsequent scraping actions only.

    # Example: (This part is commented out as it's from the previous context,
    #          but shows where the code flow continues)
    # time.sleep(2) # Give some extra time for dynamic content to load (if needed)

    # print(f"  Attempting to find attachments on {current_url}...")
    # found_attachments = []
    # try:
    #     links = driver.find_elements(By.TAG_NAME, "a")
    #     # ... attachment finding logic ...
    # except Exception as e:
    #     print(f"  Error finding attachments on {current_url}: {e}")

    # print(f"  Searching for PDFs on {current_url}...")
    # found_pdfs = []
    # try:
    #     pdf_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf')]")
    #     # ... PDF finding logic ...
    # except Exception as e:
    #     print(f"  Error searching for PDFs on {current_url}: {e}")

    # all_results[current_url] = {
    #     'attachments': found_attachments,
    #     'pdfs': found_pdfs,
    #     'status': 'Processed Successfully'
    # }

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Main loop to process each URL (context from previous step)
for current_url in url_list:
    print(f"\nProcessing URL: {current_url}")

    try:
        # Navigate to the current URL
        driver.get(current_url)

        # Wait for the page to load, ensuring the body element is present within 30 seconds
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        print(f"Navigated to URL: {current_url}") # Log successful navigation

    except TimeoutException as e:
        # Handle cases where the page takes too long to load or the element is not found
        print(f"Failed to navigate to {current_url}: Timeout Exception - {e}")
        all_results[current_url] = {'status': 'Navigation Timeout Error'}
        continue # Skip to the next URL if navigation fails

    except WebDriverException as e:
        # Catch other WebDriver-related issues during navigation (e.g., browser crash, connection error)
        print(f"Failed to navigate to {current_url}: WebDriver Exception - {e}")
        all_results[current_url] = {'status': f'Navigation WebDriver Error: {e}'}
        continue # Skip to the next URL if navigation fails

    except Exception as e:
        # Catch any other unexpected errors during the navigation process
        print(f"Failed to navigate to {current_url}: Unexpected Error - {e}")
        all_results[current_url] = {'status': f'Navigation Unexpected Error: {e}'}
        continue # Skip to the next URL if navigation fails
    
    # Placeholder for the rest of the scraping logic from the previous context:
    # For now, we'll just show where it would fit after successful navigation.
    # The rest of the original try-except block in the context should be adjusted
    # to handle exceptions for these subsequent scraping actions only.

    # Step 6: Click 'Attachments' Tab
    print('Searching for \'Attachments\' tab...')
    try:
        # Wait for the 'Attachments' tab to be clickable and then click it
        attachments_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, 'Attachments'))
        )
        attachments_tab.click()
        print('Clicked Attachments tab')
        # Give a moment for the section to load after clicking
        # time.sleep(2) # Uncomment if dynamic content needs time to load after click

    except TimeoutException:
        # If the 'Attachments' tab is not found or not clickable
        print(f'Attachments tab not found for URL: {current_url}')
        # Proceed, assuming no PDFs will be found via this path.
        # This will influence subsequent steps if they rely on the attachments tab being open.
        # No change to all_results status at this point, but subsequent PDF search might yield less.
    except Exception as e:
        # Catch any other unexpected errors during the click attempt
        print(f"An unexpected error occurred while trying to click 'Attachments' tab on {current_url}: {e}")
        # Proceed, assuming no PDFs will be found via this path.

    # Example of where previous scraping logic would continue after navigation and tab click
    found_attachments = []
    found_pdfs = []

    # Placeholder for finding attachments (e.g., specific links)
    # This part would typically involve more specific logic based on the website's structure.
    # For now, let's just log a placeholder message.
    print(f"  Attempting to find attachments on {current_url}...")
    try:
        # Example: Find all <a> tags (links) that might represent attachments
        # This is a very general approach; specific sites will need targeted selectors
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href and ("download" in href or ".zip" in href or ".rar" in href or ".tar" in href): # Simplified check
                found_attachments.append(href)
        if found_attachments:
            print(f"  Found potential attachments: {len(found_attachments)} items.")
        else:
            print("  No obvious attachments found based on a general link search.")
    except Exception as e:
        print(f"  Error finding attachments on {current_url}: {e}")

    # Placeholder for searching for PDFs
    print(f"  Searching for PDFs on {current_url}...")
    try:
        # Example: Find all <a> tags with href ending in .pdf
        pdf_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.pdf')]")
        for pdf_link in pdf_links:
            pdf_url = pdf_link.get_attribute("href")
            if pdf_url:
                found_pdfs.append(pdf_url)
        if found_pdfs:
            print(f"  Found PDFs: {len(found_pdfs)} items.")
        else:
            print("  No PDF links found.")
    except Exception as e:
        print(f"  Error searching for PDFs on {current_url}: {e}")


    # Store results for the current URL
    all_results[current_url] = {
        'attachments': found_attachments,
        'pdfs': found_pdfs,
        'status': 'Processed Successfully'
    }

# Note: The 'driver.quit()' and further processing of 'all_results' would typically follow this loop.

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

# Main loop to process each URL (context from previous step)
for current_url in url_list:
    print(f"\nProcessing URL: {current_url}")

    try:
        # Navigate to the current URL
        driver.get(current_url)

        # Wait for the page to load, ensuring the body element is present within 30 seconds
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        print(f"Navigated to URL: {current_url}") # Log successful navigation

    except TimeoutException as e:
        # Handle cases where the page takes too long to load or the element is not found
        print(f"Failed to navigate to {current_url}: Timeout Exception - {e}")
        all_results[current_url] = {'status': 'Navigation Timeout Error'}
        continue # Skip to the next URL if navigation fails

    except WebDriverException as e:
        # Catch other WebDriver-related issues during navigation (e.g., browser crash, connection error)
        print(f"Failed to navigate to {current_url}: WebDriver Exception - {e}")
        all_results[current_url] = {'status': f'Navigation WebDriver Error: {e}'}
        continue # Skip to the next URL if navigation fails

    except Exception as e:
        # Catch any other unexpected errors during the navigation process
        print(f"Failed to navigate to {current_url}: Unexpected Error - {e}")
        all_results[current_url] = {'status': f'Navigation Unexpected Error: {e}'}
        continue # Skip to the next URL if navigation fails
    
    # Step 6: Click 'Attachments' Tab
    print('Searching for \'Attachments\' tab...')
    attachments_tab_clicked = False
    try:
        # Wait for the 'Attachments' tab to be clickable and then click it
        attachments_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, 'Attachments'))
        )
        attachments_tab.click()
        attachments_tab_clicked = True
        print('Clicked Attachments tab')
        # Give a moment for the section to load after clicking
        # time.sleep(2) # Uncomment if dynamic content needs time to load after click

    except TimeoutException:
        # If the 'Attachments' tab is not found or not clickable
        print(f'Attachments tab not found for URL: {current_url}')
        # Proceed, assuming no PDFs will be found via this path.
    except Exception as e:
        # Catch any other unexpected errors during the click attempt
        print(f"An unexpected error occurred while trying to click 'Attachments' tab on {current_url}: {e}")

    # Initialize lists for attachments and PDFs for the current URL
    found_attachments = []
    found_pdfs = [] # This list will store the PDF filenames found in iframes

    # Placeholder for finding attachments (e.g., specific links)
    # This part would typically involve more specific logic based on the website's structure.
    # For now, let's just log a placeholder message.
    print(f"  Attempting to find attachments on {current_url}...")
    try:
        # Example: Find all <a> tags (links) that might represent attachments
        # This is a very general approach; specific sites will need targeted selectors
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href and ("download" in href or ".zip" in href or ".rar" in href or ".tar" in href): # Simplified check
                found_attachments.append(href)
        if found_attachments:
            print(f"  Found potential attachments: {len(found_attachments)} items.")
        else:
            print("  No obvious attachments found based on a general link search.")
    except Exception as e:
        print(f"  Error finding attachments on {current_url}: {e}")

    # --- Step 7: Find and Process Iframes for PDFs (only if attachments tab was clicked or a general search is needed) ---
    # This logic assumes it runs after trying to click the 'Attachments' tab, as that's where PDF iframes typically appear.
    print('Searching for iframe...')
    iframes = []
    try:
        # Wait for iframes to be present for up to 10 seconds (covers 5 secs page loading after clicking Attachments)
        iframes = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, 'iframe')))
        print(f'Found {len(iframes)} iframes.')
    except TimeoutException:
        print(f'No iframes found for URL: {current_url} within 10 seconds.')
    except Exception as e:
        print(f'An error occurred while trying to find iframes on {current_url}: {e}')

    # Iterate through a maximum of two found iframes
    pdf_found_in_any_iframe = False # Flag to indicate if any PDFs were found in iframes for this URL
    for i, iframe_element in enumerate(iframes[:2]): # Check up to the first two iframes
        iframe_count = i + 1
        print(f'Processing iframe {iframe_count}...')

        try:
            # Switch into the iframe
            driver.switch_to.frame(iframe_element)
            print(f'Switched into iframe {iframe_count}.')

            # Wait up to 10 seconds for <span> elements containing '.pdf' (case-insensitive)
            print(f'Searching for PDFs within iframe {iframe_count}...')
            pdf_span_elements = []
            try:
                pdf_span_elements = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//span[contains(translate(text(),'PDF','pdf'), '.pdf')]"))
                )
                print(f'Found {len(pdf_span_elements)} potential PDF elements in iframe {iframe_count}.')
            except TimeoutException:
                print(f'No PDF elements found in iframe {iframe_count} within 10 seconds.')
            except Exception as e:
                print(f"  Error waiting for PDF elements in iframe {iframe_count}: {e}")
            
            # Extract and validate text from <span> elements
            for span in pdf_span_elements:
                try:
                    pdf_filename = span.text.strip()
                    if pdf_filename and '.pdf' in pdf_filename.lower(): # Case-insensitive validation
                        found_pdfs.append(pdf_filename) # Add to the main found_pdfs list for this URL
                        print(f'Found PDF: {pdf_filename}')
                        pdf_found_in_any_iframe = True
                except StaleElementReferenceException:
                    print(f"  Warning: Stale element reference for a PDF span in iframe {iframe_count}. Skipping.")
                except Exception as e:
                    print(f"  Error processing PDF span in iframe {iframe_count}: {e}")

        except NoSuchElementException:
            print(f'Error: Could not switch to iframe {iframe_count}. Element not found or no longer valid.')
        except Exception as e:
            print(f'An unexpected error occurred while processing iframe {iframe_count}: {e}')
        finally:
            # Always switch back to default content after processing an iframe, even if errors occurred
            driver.switch_to.default_content()
            print(f'Switched back to default content from iframe {iframe_count}.')
        
        # Break the loop if PDFs are found in the current iframe or if two iframes have been checked
        if pdf_found_in_any_iframe:
            print(f'PDFs found in iframe {iframe_count}. Breaking iframe search for this URL.')
            break # Break out of the iframe iteration loop

    # Store results for the current URL
    all_results[current_url] = {
        'attachments': found_attachments,
        'pdfs': found_pdfs, # Now contains PDFs found in iframes
        'status': 'Processed Successfully'
    }

# Note: The 'driver.quit()' and further processing of 'all_results' would typically follow this loop.

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException

# Main loop to process each URL (context from previous step)
for current_url in url_list:
    print(f"\nProcessing URL: {current_url}")

    try:
        # Navigate to the current URL
        driver.get(current_url)

        # Wait for the page to load, ensuring the body element is present within 30 seconds
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        print(f"Navigated to URL: {current_url}") # Log successful navigation

    except TimeoutException as e:
        # Handle cases where the page takes too long to load or the element is not found
        print(f"Failed to navigate to {current_url}: Timeout Exception - {e}")
        all_results[current_url] = {'status': 'Navigation Timeout Error'}
        continue # Skip to the next URL if navigation fails

    except WebDriverException as e:
        # Catch other WebDriver-related issues during navigation (e.g., browser crash, connection error)
        print(f"Failed to navigate to {current_url}: WebDriver Exception - {e}")
        all_results[current_url] = {'status': f'Navigation WebDriver Error: {e}'}
        continue # Skip to the next URL if navigation fails

    except Exception as e:
        # Catch any other unexpected errors during the navigation process
        print(f"Failed to navigate to {current_url}: Unexpected Error - {e}")
        all_results[current_url] = {'status': f'Navigation Unexpected Error: {e}'}
        continue # Skip to the next URL if navigation fails
    
    # Step 6: Click 'Attachments' Tab
    print('Searching for \'Attachments\' tab...')
    attachments_tab_clicked = False
    try:
        # Wait for the 'Attachments' tab to be clickable and then click it
        attachments_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, 'Attachments'))
        )
        attachments_tab.click()
        attachments_tab_clicked = True
        print('Clicked Attachments tab')
        # Give a moment for the section to load after clicking
        # time.sleep(2) # Uncomment if dynamic content needs time to load after click

    except TimeoutException:
        # If the 'Attachments' tab is not found or not clickable
        print(f'Attachments tab not found for URL: {current_url}')
        # Proceed, assuming no PDFs will be found via this path.
    except Exception as e:
        # Catch any other unexpected errors during the click attempt
        print(f"An unexpected error occurred while trying to click 'Attachments' tab on {current_url}: {e}")

    # Initialize lists for attachments and PDFs for the current URL
    found_attachments = []
    current_url_pdfs = [] # This list will store the PDF filenames found in iframes

    # Placeholder for finding attachments (e.g., specific links)
    # This part would typically involve more specific logic based on the website's structure.
    # For now, let's just log a placeholder message.
    print(f"  Attempting to find attachments on {current_url}...")
    try:
        # Example: Find all <a> tags (links) that might represent attachments
        # This is a very general approach; specific sites will need targeted selectors
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href and ("download" in href or ".zip" in href or ".rar" in href or ".tar" in href): # Simplified check
                found_attachments.append(href)
        if found_attachments:
            print(f"  Found potential attachments: {len(found_attachments)} items.")
        else:
            print("  No obvious attachments found based on a general link search.")
    except Exception as e:
        print(f"  Error finding attachments on {current_url}: {e}")

    # --- Step 7: Find and Process Iframes for PDFs (only if attachments tab was clicked or a general search is needed) ---
    # This logic assumes it runs after trying to click the 'Attachments' tab, as that's where PDF iframes typically appear.
    print('Searching for iframe...')
    iframes = []
    try:
        # Wait for iframes to be present for up to 10 seconds (covers 5 secs page loading after clicking Attachments)
        iframes = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, 'iframe')))
        print(f'Found {len(iframes)} iframes.')
    except TimeoutException:
        print(f'No iframes found for URL: {current_url} within 10 seconds.')
    except Exception as e:
        print(f'An error occurred while trying to find iframes on {current_url}: {e}')

    # Iterate through a maximum of two found iframes
    pdf_found_in_any_iframe = False # Flag to indicate if any PDFs were found in iframes for this URL
    for i, iframe_element in enumerate(iframes[:2]): # Check up to the first two iframes
        iframe_count = i + 1
        print(f'Processing iframe {iframe_count}...')

        try:
            # Switch into the iframe
            driver.switch_to.frame(iframe_element)
            print(f'Switched into iframe {iframe_count}.')

            # Wait up to 10 seconds for <span> elements containing '.pdf' (case-insensitive)
            print(f'Searching for PDFs within iframe {iframe_count}...')
            pdf_span_elements = []
            try:
                pdf_span_elements = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//span[contains(translate(text(),'PDF','pdf'), '.pdf')]"))
                )
                print(f'Found {len(pdf_span_elements)} potential PDF elements in iframe {iframe_count}.')
            except TimeoutException:
                print(f'No PDF elements found in iframe {iframe_count} within 10 seconds.')
            except Exception as e:
                print(f"  Error waiting for PDF elements in iframe {iframe_count}: {e}")
            
            # Extract and validate text from <span> elements
            for span in pdf_span_elements:
                try:
                    pdf_filename = span.text.strip()
                    if pdf_filename and '.pdf' in pdf_filename.lower(): # Case-insensitive validation
                        current_url_pdfs.append(pdf_filename) # Add to the main current_url_pdfs list for this URL
                        print(f'Found PDF: {pdf_filename}')
                        pdf_found_in_any_iframe = True
                except StaleElementReferenceException:
                    print(f"  Warning: Stale element reference for a PDF span in iframe {iframe_count}. Skipping.")
                except Exception as e:
                    print(f"  Error processing PDF span in iframe {iframe_count}: {e}")

        except NoSuchElementException:
            print(f'Error: Could not switch to iframe {iframe_count}. Element not found or no longer valid.')
        except Exception as e:
            print(f'An unexpected error occurred while processing iframe {iframe_count}: {e}')
        finally:
            # Always switch back to default content after processing an iframe, even if errors occurred
            driver.switch_to.default_content()
            print(f'Switched back to default content from iframe {iframe_count}.')
        
        # Break the loop if PDFs are found in the current iframe or if two iframes have been checked
        if pdf_found_in_any_iframe:
            print(f'PDFs found in iframe {iframe_count}. Breaking iframe search for this URL.')
            break # Break out of the iframe iteration loop

    # Step 8: Store Results for Current URL
    # Add the list of found PDF filenames (current_url_pdfs) to the all_results dictionary,
    # using the current URL as the key. If current_url_pdfs is empty, an empty list is stored.
    all_results[current_url] = {
        'attachments': found_attachments,
        'pdfs': current_url_pdfs, # Store the list of PDFs found for the current URL
        'status': 'Processed Successfully'
    }

    # If no PDFs are found after all checks (direct search and iframe search), print a specific message.
    if not current_url_pdfs:
        print(f'No PDF elements found for URL: {current_url}')

# Note: The 'driver.quit()' and further processing of 'all_results' would typically follow this loop.

# This block will execute after all URLs have been processed or if an error occurred earlier
# during the processing loop, but only if the driver was successfully initialized.
if driver is not None:
    try:
        driver.quit()
        print("\nWebDriver quit successfully.")
    except Exception as e:
        # Catch any exceptions that might occur during the quit process
        print(f"\nError quitting WebDriver: {e}")
else:
    print("\nWebDriver was not initialized or had already quit.")

# Print Summary of Results
print("\n===== Summary of All Results =====")
for url, data in all_results.items():
    print(f"\nURL: {url}")
    found_pdfs = data.get('pdfs', []) # Get the list of PDFs, default to empty list if key not present

    if found_pdfs:
        print("  Found PDF Filenames:")
        for pdf_filename in found_pdfs:
            print(f"    - {pdf_filename}")
    else:
        print("  No PDFs found.")
print("\n===== End of Summary =====")