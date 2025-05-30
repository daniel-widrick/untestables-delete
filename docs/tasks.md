# **Github Repository Test Finder**

This document outlines the requirements for an application designed to identify Python projects on GitHub that lack unit testing and have a star count within a specified range. The goal is to help developers find repositories that could benefit from unit test contributions.

## **Analyzer Service Tasks:**

1. Configuration Management

- [x] Load Configuration from .env file
  - [x] Define the overall desired star range for scanning (e.g., absolute min_stars, absolute max_stars for the entire project).
  - [x] Set a default "chunk size" or "scan increment" (e.g., 100 stars, as you mentioned, for breaking down large gaps).
  - [x] Store the command template or path to the scanner (e.g., poetry run untestables).

2. Database Interaction

- [ ] Implement a function to query the database and determine which star numbers or star ranges have already been successfully processed by the scanner.
- Consider how this is stored: Does the scanner log (min_stars, max_stars, status) for each run, or do you infer this from the star counts of collected repositories? The former is often easier for gap analysis.

3. Gap Identification Logic

- [ ] Fetch Processed Ranges:
  - Retrieve the sorted list of distinct star counts or successfully scanned ranges from the database.
- [ ] Calculate Missing Ranges ("Gaps"):
  - Compare the processed ranges against your configured overall desired star range.
  - Identify all contiguous blocks of star numbers that have not been scanned.
  - If a very large gap is found, plan to break it down into smaller chunks based on the configured "chunk size."

5. Scanner Invocation and Management

- [ ] Gap Selection and Prioritization:
  - If no scanner is active and gaps exist, select a gap to process. (Strategy: e.g., the lowest available star range first, or the smallest gap).
- [ ] Determine Scan Parameters:
  - For the selected gap, calculate the min_stars and max_stars for the next scanner run. This should not exceed your configured "chunk size" (e.g., if a gap is 500-1000 and chunk size is 100, the next scan would be min_stars=500, max_stars=600).
- [ ] Construct Scanner Command:
  - Dynamically build the full command string, for example: poetry run untestables --min-stars <calculated_min> --max-stars <calculated_max>.
- [ ] Execute Scanner:
  - Run the scanner command as a subprocess.
- [ ] Wait for the scanner subprocess to complete.
- [ ] Handle Scanner Output:
  - Capture the scanner's exit code.
  - Optionally, capture stdout and stderr for logging.
- [ ] If the scanner indicates partial completion (e.g., due to API limits), the analyzer might need to log this or adjust its understanding of the remaining gap.

6. Logging and Monitoring

- [ ] Implement Comprehensive Logging:
  - Log key actions: script start/end, configuration used, database connection status.
  - Log identified gaps.
  - Log when the scanner is invoked, including the min_stars and max_stars passed.
  - Log the scanner's completion status (success/failure, exit code).
  - Log errors encountered by the analyzer itself.

7. Operational Control

- [ ] Define Execution Mode:
  - Decide if the analyzer runs once and exits, or if it runs in a loop.
  - If looping, include a sleep interval between checks (e.g., after a scan finishes, or if no gaps are found, or if the scanner is busy).
- [ ] Handle "No Gaps" Scenario:
  - If no gaps are found, log this state and either exit gracefully or enter a waiting period before checking again.
- [ ] Handle "Scanner Busy" Scenario:
  - If the scanner is found to be already running, log this and wait before re-checking.

## **1. Core Repository Discovery & Filtering**

### **GitHub API Integration**

- [x] Securely connect to the GitHub API using authentication tokens (OAuth or Personal Access Tokens).
- [x] Manage API rate limits gracefully (e.g., request throttling, user alerts).
- [x] Support pagination to retrieve large datasets.

### **Search Criteria**

- [x] Filter repositories based on:
  - Primary language set to Python.
  - Star count range (e.g., 5 to 1,000 stars).
  - Additional keyword searches in repository descriptions.

### **Initial Data Extraction**

- [x] Retrieve repository metadata including:
  - Name
  - Description
  - Star count
  - Repository URL
- [x] Store search results for further processing.

## **2. Unit Test Presence Detection**

### **Detecting Test Files & Directories**

- [x] Check for the existence of common unit test directories: tests/, test/.
- [x] Identify common unit test files (test\_\*.py, \*\_test.py).
- [x] Scan for configuration files related to testing (pytest.ini, tox.ini, nose.cfg).

### **README & Project Metadata Analysis**

- [x] Search repository README for mentions of testing frameworks (pytest, unittest, nose).
- [x] Detect CI/CD configurations related to testing (GitHub Actions, Travis CI).

### **Reporting on Missing Tests**

- [x] Flag repositories where unit testing frameworks and configurations are absent
- [x] Maintain a structured list of repositories needing unit tests.

## **4. Application Configuration & Usability**

### **Command-Line Interface (CLI)**

- [x] Provide arguments for customization:
  - Star range (--min-stars, --max-stars).
  - Custom search queries (--query).
  - Output file formats (--output csv/json/md).

### **Error Handling & API Limits**

- [x] Implement retry logic for failed requests.
- [x] Offer user-friendly error messages when exceeding API limits.

## **5. CI/CD Documentation (For Future Expansion)**

### **Overview of CI/CD Pipeline (Documentation Only)**

- [x] Explain how repositories could integrate:
  - Automated unit test execution.
  - Static analysis tools (e.g., Flake8, Pylint).
  - Continuous Integration with GitHub Actions.
- [x] Provide instructions on how to set up test automation.
