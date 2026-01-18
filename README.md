# Java Submission Testing Automation

Automatically test student Java submissions by recursively processing zip files and validating them against a default App.java reference implementation.

## Features

- ✅ **Recursive Zip Processing** - Finds and tests all student submissions
- ✅ **Smart File Handling** - Detects file locations (root, src/, nested folders)
- ✅ **Package Cleanup** - Optionally removes package declarations to avoid conflicts
- ✅ **Output Validation** - Compares program output against expected results
- ✅ **Selective Testing** - Test all students or specific ones with `--check-stuid`
- ✅ **Dual Reports** - Generates JSON (detailed) and CSV (summary) reports
- ✅ **Error Tracking** - Captures compilation/execution errors with full details
- ✅ **Cross-Platform** - Works on Windows, macOS, Linux
- ✅ **Setup Automation** - One-command project initialization

## Project Structure

```
d:/JAVA AUTOMATION/
├── default_code/              # Reference implementation
│   └── App.java
├── submissions/               # Student submissions (organized by student ID)
│   ├── 6838205621/
│   │   └── submission.zip
│   ├── 6838209221/
│   │   └── homework.zip
│   └── ...
├── test_results/              # Auto-generated test reports
│   ├── results_20260118_101530.json
│   ├── results_20260118_101530.csv
│   └── ...
├── temp_extracts/             # Temporary extraction directory (auto-cleanup)
├── java_submission_tester.py  # Main testing engine
├── setup.py                   # Project initializer
├── expected_output.txt        # Expected output template
├── README.md                  # This file
└── .gitignore                 # Git ignore rules
```

## How It Works

1. **Extraction** - Extracts each student's zip file to a temporary directory
2. **Cleanup** - Removes duplicate App.java and package declarations (optional)
3. **File Detection** - Intelligently finds Java files in any directory structure
4. **Compilation** - Compiles all Java files together using `javac`
5. **Execution** - Runs the program and captures output
6. **Validation** - Compares output against expected results (optional)
7. **Reporting** - Generates JSON and CSV reports with detailed error info

## Quick Start

### 1. Initialize Project
```powershell
python setup.py
```
Creates directories, templates, and documentation.

### 2. Add Student Submissions
Place student zips in organized folders:
```
submissions/
├── 6838205621/
│   └── submission.zip
├── 6838209221/
│   └── homework.zip
```

### 3. Run Tests
```powershell
# Test all students
python java_submission_tester.py --cleanup

# Test specific students
python java_submission_tester.py --check-stuid 6838205621 6838209221 --cleanup

# With output validation and package removal
python java_submission_tester.py --expected expected_output.txt --remove-pack --cleanup
```

### 4. Review Results
Check `test_results/` for:
- `results_*.json` - Detailed test results
- `results_*.csv` - Summary report (Student ID, Status, Remark)

## Command-Line Options

```powershell
python java_submission_tester.py [OPTIONS]
```

### Available Options:

| Option | Example | Description |
|--------|---------|-------------|
| `--submissions DIR` | `--submissions "path/to/zips"` | Student submissions directory (default: `submissions`) |
| `--default DIR` | `--default "path/to/code"` | Reference code directory (default: `default_code`) |
| `--results DIR` | `--results "path/to/results"` | Results output directory (default: `test_results`) |
| `--expected FILE` | `--expected expected_output.txt` | Expected output file for validation (optional) |
| `--remove-pack` | `--remove-pack` | Remove package declarations from Java files (optional) |
| `--check-stuid ID...` | `--check-stuid 6838205621 6838209221` | Test only specific student IDs (optional, space-separated) |
| `--cleanup` | `--cleanup` | Delete temporary extraction files after testing |
| `--help` | `--help` | Show help message |

## Student Submission Format

Each student must submit a `.zip` file in their own folder:

```
submissions/
├── 6838205621/
│   └── submission.zip
│       ├── Doll.java
│       ├── Barbie.java
│       ├── TeddyDoll.java
│       └── PorcelainDoll.java
├── 6838209221/
│   └── homework.zip
│       └── src/
│           ├── Doll.java
│           ├── Barbie.java
│           ├── TeddyDoll.java
│           └── PorcelainDoll.java
└── 6838313821/
    └── lab02.zip
        └── Lab02/
            ├── Doll.java
            ├── Barbie.java
            ├── TeddyDoll.java
            └── PorcelainDoll.java
```

**Key Points:**
- Folder name = **Student ID** (any format: `6838205621`, `student001`, etc.)
- Any zip filename accepted: `submission.zip`, `homework.zip`, `lab02.zip`
- Java files can be in:
  - Root directory
  - `src/` subfolder
  - Any nested folder structure
- **Do NOT include App.java** - reference version will be used automatically
- Package declarations (`package lab2;`) are automatically handled

## Output Reports

### JSON Report (`results_*.json`)
Detailed results for each student:
```json
{
  "student_id": "6838205621",
  "overall_status": "PASSED",
  "extraction": {
    "success": true
  },
  "compilation": {
    "success": true,
    "output": "Compilation successful"
  },
  "execution": {
    "success": true,
    "output": "Name: Barbie1\nMaterial: Plastic\n..."
  },
  "output_validation": {
    "success": true,
    "message": "Output matches expected"
  }
}
```

### CSV Report (`results_*.csv`)
Quick summary for grading:
```
Student ID,Status,Remark
6838205621,PASSED,All tests passed
6838209221,FAILED,Compilation: error: cannot find symbol Doll[] dolls
6838313821,FAILED,Output: Output mismatch: Expected 10 lines, got 8 lines
```

## Setting Up Default App.java

Edit `default_code/App.java` with your reference implementation:

```java
public class App {
    public static void main(String[] args) {
        Doll[] dolls = new Doll[5];

        dolls[0] = new Barbie("Barbie1", 29.99);
        dolls[1] = new Barbie("Barbie2", 34.99);
        dolls[2] = new TeddyDoll("Teddy", 19.99);
        dolls[3] = new PorcelainDoll("Porcelain1", 49.99);
        dolls[4] = new PorcelainDoll("Porcelain2", 59.99);

        for (Doll doll : dolls) {
            doll.display();
            doll.play();
            System.out.println();
        }
    }
}
```

## Setting Up Expected Output

Edit `expected_output.txt` with your expected program output:

```
Name: Barbie1
Material: Plastic
Price: $29.99
Barbie sings: I'm a Barbie girl in a Barbie world!

Name: Barbie2
Material: Plastic
Price: $34.99
Barbie sings: I'm a Barbie girl in a Barbie world!

...
```

Then run tests with:
```powershell
python java_submission_tester.py --expected expected_output.txt --cleanup
```

## Usage Examples

### Example 1: Test All Students
```powershell
python java_submission_tester.py --cleanup
```

**Output:**
```
============================================================
Java Submission Tester
============================================================
Found 3 submission zip files

Testing 6838205621...
  ✓ Extracted: 6838205621
  ✓ Copied default App.java
  ✓ Found 4 Java file(s)
  ✓ Compilation successful
  ✓ Execution successful

Testing 6838209221...
  ✓ Extracted: 6838209221
  ✗ Compilation failed
    error: cannot find symbol

...

============================================================
TEST SUMMARY
============================================================
Total submissions: 3
Passed: 1
Failed: 2
```

### Example 2: Test Specific Students With Output Validation
```powershell
python java_submission_tester.py `
  --check-stuid 6838205621 6838209221 `
  --expected expected_output.txt `
  --cleanup
```

### Example 3: Remove Package Declarations
```powershell
python java_submission_tester.py `
  --remove-pack `
  --cleanup
```

Automatically strips `package lab2;` declarations from student files.

### Example 4: All Options Combined
```powershell
python java_submission_tester.py `
  --submissions "C:\submissions" `
  --default "C:\reference" `
  --results "C:\grades" `
  --expected "C:\expected_output.txt" `
  --check-stuid 6838205621 6838209221 6838313821 `
  --remove-pack `
  --cleanup
```

## Troubleshooting

### "javac not found"
- Install Java JDK from [oracle.com](https://www.oracle.com/java/technologies/downloads/)
- Add Java `bin` directory to system PATH

### "cannot find symbol: class Doll"
- Student didn't submit required helper classes
- Ensure `default_code/` contains all necessary Java files
- Or provide the missing classes to students

### "duplicate class: App"
- Student submitted their own App.java
- Script automatically removes it and uses the reference version

### "package lab2 conflicts"
- Student files have `package` declarations
- Use `--remove-pack` flag to automatically strip them

### "No zip files found"
- Check folder structure: `submissions/student_id/submission.zip`
- Zip filenames must end with `.zip`

## Advanced Features

### Selective Testing
Test only specific students without running the entire batch:
```powershell
python java_submission_tester.py --check-stuid 6838205621 6838209221
```

### Output Validation
Compare student output against expected results:
```powershell
python java_submission_tester.py --expected expected_output.txt
```

### Package Cleanup
Remove `package` declarations to avoid conflicts:
```powershell
python java_submission_tester.py --remove-pack
```

### Temp File Cleanup
Automatically delete extraction files to save space:
```powershell
python java_submission_tester.py --cleanup
```

## File Structure Details

| File/Folder | Purpose |
|-------------|---------|
| `java_submission_tester.py` | Main testing engine |
| `setup.py` | Project initialization script |
| `default_code/App.java` | Reference implementation (edit this) |
| `expected_output.txt` | Expected program output (optional) |
| `test_results/` | Auto-generated JSON and CSV reports |
| `temp_extracts/` | Temporary student extraction (auto-cleanup) |
| `submissions/` | Student submission zips (organized by ID) |
| `.gitignore` | Git ignore rules (don't upload temp files) |
| `README.md` | This documentation |
- **Cross-platform**: Works on Windows, macOS, and Linux
