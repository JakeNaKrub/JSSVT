# Java Submission Testing Automation - Project Instructions

## Project Overview
Python-based automation system to recursively process student Java submission zip files and test them against a default App.java reference implementation.

## Key Features
- Recursively finds and processes all student zip files
- Extracts submissions to temporary directories
- Compiles Java code with javac
- Executes App.java and captures output
- Generates JSON test reports with pass/fail status
- Cross-platform support (Windows, macOS, Linux)

## Project Structure
```
d:/JAVA AUTOMATION/
├── default_code/               # Reference App.java with main()
├── submissions/                # Student zip file submissions
├── test_results/               # JSON test result reports
├── java_submission_tester.py   # Main Python tester script
└── README.md                   # Full documentation
```

## Usage
```powershell
python java_submission_tester.py [--submissions DIR] [--default DIR] [--results DIR] [--cleanup]
```

## Requirements
- Python 3.7+
- Java JDK (javac and java commands)

## Completion Status
- ✓ Project structure created
- ✓ Default App.java template provided
- ✓ Main testing script implemented
- ✓ Documentation complete
- ✓ Ready for use
