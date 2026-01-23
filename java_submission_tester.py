import os
import sys
import zipfile
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import re

class JavaSubmissionTester:
    """
    Recursively process student Java submission zips and test them.
    
    Workflow:
    1. Find all .zip files in submissions directory
    2. Extract each zip file into a temporary directory
    3. Compile Java files (including default App.java)
    4. Execute and capture output
    5. Generate test report
    """
    
    def __init__(self, 
                 submissions_dir: str = "submissions",
                 default_code_dir: str = "default_code",
                 results_dir: str = "test_results",
                 expected_output: Optional[str] = None,
                 remove_packages: bool = False,
                 check_students: Optional[List[str]] = None,
                 verbose: bool = False):
        """
        Initialize the Java submission tester.
        
        Args:
            submissions_dir: Directory containing student zip files
            default_code_dir: Directory with default App.java
            results_dir: Directory to store test results
            expected_output: Expected output to compare against (optional)
            remove_packages: Whether to remove package declarations (default: False)
            check_students: List of specific student IDs to test (optional, tests all if None)
        """
        self.submissions_dir = Path(submissions_dir)
        self.default_code_dir = Path(default_code_dir)
        self.results_dir = Path(results_dir)
        self.temp_extract_dir = Path("temp_extracts")
        self.expected_output = expected_output
        self.remove_packages = remove_packages
        self.check_students = check_students
        self.verbose = verbose
        
        # Create directories if they don't exist
        self.submissions_dir.mkdir(exist_ok=True)
        self.default_code_dir.mkdir(exist_ok=True)
        self.results_dir.mkdir(exist_ok=True)
        self.temp_extract_dir.mkdir(exist_ok=True)
        
        self.test_results = []
    def find_java_files(self, directory: Path) -> List[Path]:
        """
        Recursively find all valid .java files.
        Filters out __MACOSX and hidden metadata files starting with ._
        """
        java_files = []
        for java_file in directory.rglob("*.java"):
            # Filter 1: Skip macOS system directory
            if "__MACOSX" in java_file.parts:
                continue
            
            # Filter 2: Skip macOS hidden metadata files (Fixes the utf-8 error)
            if java_file.name.startswith("._"):
                continue
                
            java_files.append(java_file)
        return java_files
    
    def find_submission_zips(self) -> List[Path]:
        """
        Find all .zip files in student_id folders.
        Expected structure: submissions/student_id/*.zip
        If check_students is specified, only those students are included.
        
        Returns:
            List of tuples (student_id, zip_path)
        """
        submissions = []
        
        # Iterate through student ID folders
        for student_folder in self.submissions_dir.iterdir():
            if student_folder.is_dir():
                student_id = student_folder.name
                
                # Filter by check_students if specified
                if self.check_students and student_id not in self.check_students:
                    continue
                
                # Find zip files in each student folder
                zip_files = list(student_folder.glob("*.zip"))
                for zip_file in zip_files:
                    submissions.append((student_id, zip_file))
        
        print(f"Found {len(submissions)} submission zip files")
        return submissions
    
    def extract_zip(self, zip_path: Path, student_id: str) -> Optional[Path]:
        """
        Extract a zip file to temporary directory.
        
        Args:
            zip_path: Path to the zip file
            student_id: Student ID for organizing extraction
            
        Returns:
            Path to extracted directory, or None if extraction fails
        """
        try:
            # Create unique extraction directory using student ID
            extract_path = self.temp_extract_dir / student_id
            
            # Clean up existing extraction
            if extract_path.exists():
                shutil.rmtree(extract_path)
            
            extract_path.mkdir(parents=True, exist_ok=True)
            
            # Extract zip
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            
            print(f"  ✓ Extracted: {student_id}")
            return extract_path
        
        except Exception as e:
            print(f"  ✗ Failed to extract {zip_path}: {e}")
            return None
    
    def find_java_files(self, directory: Path) -> List[Path]:
        """
        Recursively find all .java files in directory.
        Ignores __MACOSX and other system folders.
        
        Args:
            directory: Directory to search
            
        Returns:
            List of Path objects for Java files
        """
        java_files = []
        for java_file in directory.rglob("*.java"):
            # Skip files in __MACOSX or other system directories
            if "__MACOSX" not in java_file.parts and ".DS_Store" not in java_file.name:
                java_files.append(java_file)
        return java_files
    
    def compile_java_files(self, work_dir: Path, java_files: List[Path]) -> Tuple[bool, str]:
        """
        Compile Java files using javac.
        Handles files nested in src/ folders or other subdirectories.
        
        Args:
            work_dir: Working directory
            java_files: List of Java files to compile
            
        Returns:
            Tuple of (success: bool, output: str)
        """
        if not java_files:
            return False, "No Java files found"
        
        try:
            # Get relative paths from work_dir
            rel_files = [str(f.relative_to(work_dir)) for f in java_files]
            
            # Create output directory for compiled classes
            out_dir = work_dir / "bin"
            out_dir.mkdir(exist_ok=True)
            
            # Build source path - include all parent directories that might contain source files
            source_dirs = set()
            for java_file in java_files:
                # Add all parent directories that are in the project
                parent = java_file.parent
                while parent != work_dir and parent.is_relative_to(work_dir):
                    source_dirs.add(parent)
                    parent = parent.parent
            
            # Compile with output directory
            cmd = ["javac", "-d", str(out_dir)] + rel_files
            result = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return True, "Compilation successful"
            else:
                return False, result.stderr
        
        except subprocess.TimeoutExpired:
            return False, "Compilation timed out (30 seconds)"
        except FileNotFoundError:
            return False, "javac not found - ensure Java is installed"
        except Exception as e:
            return False, str(e)
    
    def run_app(self, work_dir: Path) -> Tuple[bool, str]:
        """
        Run App.java using java command.
        Looks for compiled classes in bin/ directory or root.
        
        Args:
            work_dir: Working directory where App.class is located
            
        Returns:
            Tuple of (success: bool, output: str)
        """
        try:
            # Try bin directory first (where compiled classes are placed)
            bin_dir = work_dir / "bin"
            classpath = str(bin_dir) if bin_dir.exists() else "."
            
            cmd = ["java", "-cp", classpath, "App"]
            result = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            output = result.stdout + result.stderr
            success = result.returncode == 0
            
            return success, output
        
        except subprocess.TimeoutExpired:
            return False, "Execution timed out (10 seconds)"
        except Exception as e:
            return False, f"Error running App: {str(e)}"
    
    def compare_output(self, actual: str, expected: str) -> Tuple[bool, str]:
        import re

        # Split into lines but KEEP empty lines to maintain index integrity
        actual_lines = actual.splitlines()
        expected_lines = expected.splitlines()

        # Determine the range to check (longest file)
        max_lines = max(len(actual_lines), len(expected_lines))

        for i in range(max_lines):
            line_num = i + 1
            
            # Get line content or empty string if one file is shorter than the other
            act_line = actual_lines[i].strip() if i < len(actual_lines) else None
            exp_line = expected_lines[i].strip() if i < len(expected_lines) else None

            # 1. Handle cases where one file ends early
            if act_line is None or exp_line is None:
                return False, f"Mismatch at line {line_num}: One file ended unexpectedly."

            # 2. If both lines are empty after stripping, they "match" - move to next
            if not act_line and not exp_line:
                continue

            # 3. Soft Clean for comparison (ignore colons, dollar signs, punctuation)
            def soft_clean(text):
                # Remove punctuation except decimals
                cleaned = re.sub(r'[^a-zA-Z0-9.\s]', '', text)
                return cleaned.lower().split()

            act_tokens = soft_clean(act_line)
            exp_tokens = soft_clean(exp_line)

            # 4. Compare tokens within the line
            is_match = True
            if len(act_tokens) != len(exp_tokens):
                is_match = False
            else:
                for a_tok, e_tok in zip(act_tokens, exp_tokens):
                    try:
                        # Numeric check
                        if abs(float(a_tok) - float(e_tok)) > 0.02:
                            is_match = False
                            break
                    except ValueError:
                        # Text check
                        if a_tok != e_tok:
                            is_match = False
                            break

            if not is_match:
                return False, (f"Mismatch at line {line_num}:\n"
                            f"  Expected: \"{expected_lines[i]}\"\n"
                            f"  Actual:   \"{actual_lines[i]}\"")

        return True, "Output matches expected"
    def test_submission(self, student_id: str, zip_path: Path) -> Dict:
            print(f"\nTesting {student_id}...")
            
            result = {
                "student_id": student_id,
                "zip_file": str(zip_path),
                "timestamp": datetime.now().isoformat(),
                "extraction": {"success": False},
                "compilation": {"success": False},
                "execution": {"success": False},
                "overall_status": "FAILED"
            }
            
            # Step 1: Extract submission
            extract_path = self.extract_zip(zip_path, student_id)
            if not extract_path:
                return result
            result["extraction"]["success"] = True

            if self.remove_packages:
            # CHANGED: Use self.find_java_files() instead of extract_path.rglob()
            # This ensures we only process the "clean" list of files
                for java_file in self.find_java_files(extract_path):
                    try:
                        content = java_file.read_text(encoding='utf-8')
                        
                        # Remove package declarations
                        updated = re.sub(r'^\s*package\s+[\w.]+\s*;', '', content, flags=re.MULTILINE)
                        
                        if updated != content:
                            java_file.write_text(updated, encoding='utf-8')
                            print(f"  ✓ Removed package declaration from {java_file.name}")
                    except Exception as e:
                        print(f"  ⚠ Could not process {java_file.name}: {e}")

            # Step 3: Find and Replace App.java ONLY
            # We look for where the student put their App.java to replace it in-place
            student_app_files = list(extract_path.rglob("App.java"))
            default_app = self.default_code_dir / "App.java"
            
            if not default_app.exists():
                print(f"  ✗ Error: Master App.java not found in {self.default_code_dir}")
                return result

            if student_app_files:
                for app_file in student_app_files:
                    if "__MACOSX" not in app_file.parts:
                        shutil.copy(default_app, app_file)
                        print(f"  ✓ Replaced student's App.java at: {app_file.relative_to(extract_path)}")
            else:
                # If they didn't provide an App.java, we place it in the root or 'src'
                target = extract_path / "src" if (extract_path / "src").exists() else extract_path
                shutil.copy(default_app, target / "App.java")
                print(f"  ✓ App.java not found in zip; injected into {target.relative_to(extract_path)}/")

            # Step 4: Find all Java files (keeping original structure)
            java_files = self.find_java_files(extract_path)
            if not java_files:
                result["compilation"]["error"] = "No Java files found"
                return result
            
            # Step 5: Compile (Uses -d bin to keep source tree clean)
            compile_success, compile_output = self.compile_java_files(extract_path, java_files)
            result["compilation"]["success"] = compile_success
            result["compilation"]["output"] = compile_output
            
            if not compile_success:
                print(f"  ✗ Compilation failed")
                return result

            # Step 6: Execute and Validate
            exec_success, exec_output = self.run_app(extract_path)
            result["execution"]["success"] = exec_success
            result["execution"]["output"] = exec_output
            
            if exec_success:
                if self.expected_output:
                    match, message = self.compare_output(exec_output, self.expected_output)
                    result["output_validation"] = {"success": match, "message": message}
                    result["overall_status"] = "PASSED" if match else "FAILED"
                    print(f"  {'✓' if match else '✗'} Output validation {'passed' if match else 'failed'}")
                else:
                    result["overall_status"] = "PASSED"
                    print(f"  ✓ Execution successful")
            else:
                print(f"  ✗ Execution failed")

            return result
    
    def run_all_tests(self) -> List[Dict]:
        """
        Find and test all student submissions.
        
        Returns:
            List of test result dictionaries
        """
        print("=" * 60)
        print("Java Submission Tester")
        print("=" * 60)
        
        zip_files = self.find_submission_zips()
        
        if not zip_files:
            print("No zip files found in submissions/student_id/ directories!")
            return []
        
        # Test each submission
        for student_id, zip_path in zip_files:
            result = self.test_submission(student_id, zip_path)
            self.test_results.append(result)
        
        # Save results
        self.save_results()
        self.save_csv_report()
        self.print_summary()
        
        return self.test_results
    
    def save_results(self) -> None:
        """Save test results to JSON file."""
        output_file = self.results_dir / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(output_file, 'w') as f:
                json.dump(self.test_results, f, indent=2)
            print(f"✓ Results saved to: {output_file}")
        except Exception as e:
            print(f"Error saving results: {e}")
    
    def save_csv_report(self) -> None:
        """Save test results to CSV file."""
        import csv
        
        output_file = self.results_dir / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Write header
                writer.writerow(["Student ID", "Status", "Remark"])
                
                # Write results
                for result in self.test_results:
                    student_id = result.get("student_id", "Unknown")
                    status = result.get("overall_status", "UNKNOWN")
                    
                    # Build remark based on what failed
                    remark = ""
                    if status == "PASSED":
                        remark = "All tests passed"
                    else:
                        # Collect error messages
                        errors = []
                        
                        if not result.get("extraction", {}).get("success"):
                            errors.append("Extraction failed")
                        
                        if not result.get("compilation", {}).get("success"):
                            comp_error = result.get("compilation", {}).get("output", "Compilation error")
                            # Truncate long error messages
                            if len(comp_error) > 100:
                                comp_error = comp_error[:100] + "..."
                            errors.append(f"Compilation: {comp_error}")
                        
                        if not result.get("execution", {}).get("success"):
                            exec_error = result.get("execution", {}).get("output", "Execution error")
                            if len(exec_error) > 100:
                                exec_error = exec_error[:100] + "..."
                            errors.append(f"Execution: {exec_error}")
                        
                        if result.get("output_validation", {}).get("success") == False:
                            val_msg = result.get("output_validation", {}).get("message", "Output validation failed")
                            errors.append(f"Output: {val_msg}")
                        
                        remark = " | ".join(errors) if errors else "Unknown error"
                    
                    writer.writerow([student_id, status, remark])
            
            print(f"✓ CSV report saved to: {output_file}")
        except Exception as e:
            print(f"Error saving CSV report: {e}")
    
    def print_summary(self) -> None:
        """Print summary of test results."""
        passed = sum(1 for r in self.test_results if r["overall_status"] == "PASSED")
        failed = len(self.test_results) - passed
        
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Total submissions: {len(self.test_results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print()
        
        for result in self.test_results:
            status_icon = "✓" if result["overall_status"] == "PASSED" else "✗"
            print(f"{status_icon} {result['student_id']}: {result['overall_status']}")
    
    def cleanup(self) -> None:
        """Clean up temporary extraction directory."""
        try:
            if self.temp_extract_dir.exists():
                shutil.rmtree(self.temp_extract_dir)
            print("\n✓ Cleaned up temporary files")
        except Exception as e:
            print(f"Warning: Could not cleanup temp files: {e}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test Java submissions from student zip files"
    )
    parser.add_argument(
        "--submissions",
        default="submissions",
        help="Directory containing student zip files (default: submissions)"
    )
    parser.add_argument(
        "--default",
        default="default_code",
        help="Directory with default App.java (default: default_code)"
    )
    parser.add_argument(
        "--results",
        default="test_results",
        help="Directory to store results (default: test_results)"
    )
    parser.add_argument(
        "--expected",
        default=None,
        help="File containing expected output for validation (optional)"
    )
    parser.add_argument(
        "--remove-pack",
        action="store_true",
        help="Remove package declarations from student files (optional)"
    )
    parser.add_argument(
        "--check-stuid",
        nargs="+",
        default=None,
        help="Test only specific student IDs (space-separated) (optional)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full execution output for each submission"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up temporary extraction directory after testing"
    )
    
    args = parser.parse_args()
    
    # Load expected output if provided
    expected_output = None
    if args.expected:
        try:
            with open(args.expected, 'r') as f:
                expected_output = f.read()
            print(f"Loaded expected output from: {args.expected}\n")
        except FileNotFoundError:
            print(f"Warning: Expected output file not found: {args.expected}\n")
    
    # Run tests
    tester = JavaSubmissionTester(
        submissions_dir=args.submissions,
        default_code_dir=args.default,
        results_dir=args.results,
        expected_output=expected_output,
        remove_packages=args.remove_pack,
        check_students=args.check_stuid,
        verbose=args.verbose
    )
    
    try:
        tester.run_all_tests()
    finally:
        if args.cleanup:
            tester.cleanup()


if __name__ == "__main__":
    main()
