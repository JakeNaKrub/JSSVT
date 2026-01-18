import os
import sys
import zipfile
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple


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
                 check_students: Optional[List[str]] = None):
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
        
        # Create directories if they don't exist
        self.submissions_dir.mkdir(exist_ok=True)
        self.default_code_dir.mkdir(exist_ok=True)
        self.results_dir.mkdir(exist_ok=True)
        self.temp_extract_dir.mkdir(exist_ok=True)
        
        self.test_results = []
    
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
        """
        Compare actual output with expected output.
        
        Args:
            actual: Actual program output
            expected: Expected program output
            
        Returns:
            Tuple of (match: bool, message: str)
        """
        # Normalize whitespace for comparison
        actual_lines = [line.strip() for line in actual.strip().split('\n') if line.strip()]
        expected_lines = [line.strip() for line in expected.strip().split('\n') if line.strip()]
        
        if actual_lines == expected_lines:
            return True, "Output matches expected"
        else:
            # Return mismatch details
            diff_msg = f"Output mismatch:\nExpected {len(expected_lines)} lines, got {len(actual_lines)} lines"
            return False, diff_msg
    
    def test_submission(self, student_id: str, zip_path: Path) -> Dict:
        """
        Test a single student submission.
        
        Args:
            student_id: Student ID folder name
            zip_path: Path to student zip file
            
        Returns:
            Dictionary with test results
        """
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
        
        # Step 2: Optionally remove package declarations from student files
        # This allows all classes to work together without package conflicts
        if self.remove_packages:
            for java_file in extract_path.rglob("*.java"):
                if "__MACOSX" not in java_file.parts:
                    try:
                        with open(java_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Remove package declarations
                        updated_content = content
                        import re
                        updated_content = re.sub(r'^\s*package\s+[\w.]+\s*;', '', updated_content, flags=re.MULTILINE)
                        
                        if updated_content != content:
                            with open(java_file, 'w', encoding='utf-8') as f:
                                f.write(updated_content)
                            print(f"  ✓ Removed package declaration from {java_file.name}")
                    except Exception as e:
                        print(f"  ⚠ Could not process {java_file.name}: {e}")
        
        # Step 3: Remove student's App.java and copy default App.java
        # Delete any student-submitted App.java to avoid duplicate class error
        for app_file in extract_path.rglob("App.java"):
            if "__MACOSX" not in app_file.parts:
                app_file.unlink()
                print(f"  ✓ Removed student's App.java")
        
        # Step 4: Find where student's Java files are located
        # Copy App.java to the same directory as student's Java files
        student_java_files = []
        for java_file in extract_path.rglob("*.java"):
            if "__MACOSX" not in java_file.parts and ".DS_Store" not in java_file.name:
                student_java_files.append(java_file)
        
        # Find the directory containing student's Java files
        target_dir = extract_path
        if student_java_files:
            # Get the most common parent directory
            parent_dirs = {}
            for java_file in student_java_files:
                parent = java_file.parent
                parent_dirs[parent] = parent_dirs.get(parent, 0) + 1
            # Use the directory with most Java files
            target_dir = max(parent_dirs, key=parent_dirs.get)
        
        # Copy default App.java to the target directory
        default_app = self.default_code_dir / "App.java"
        if default_app.exists():
            shutil.copy(default_app, target_dir / "App.java")
            print(f"  ✓ Copied default App.java to {target_dir.relative_to(extract_path) if target_dir != extract_path else 'root'}/")
        else:
            print(f"  ✗ Default App.java not found")
        
        # Step 5: Find all Java files
        java_files = self.find_java_files(extract_path)
        if not java_files:
            result["compilation"]["error"] = "No Java files found in submission"
            return result
        
        print(f"  ✓ Found {len(java_files)} Java file(s)")
        
        # Step 6: Compile
        compile_success, compile_output = self.compile_java_files(extract_path, java_files)
        result["compilation"]["success"] = compile_success
        result["compilation"]["output"] = compile_output
        
        if compile_success:
            print(f"  ✓ Compilation successful")
        else:
            print(f"  ✗ Compilation failed")
            print(f"    {compile_output[:200]}")
            return result
        
        # Step 7: Execute
        exec_success, exec_output = self.run_app(extract_path)
        result["execution"]["success"] = exec_success
        result["execution"]["output"] = exec_output
        
        if exec_success:
            print(f"  ✓ Execution successful")
            
            # Step 8: Compare output if expected output is defined
            if self.expected_output:
                output_match, match_msg = self.compare_output(exec_output, self.expected_output)
                result["output_validation"] = {
                    "success": output_match,
                    "message": match_msg
                }
                
                if output_match:
                    print(f"  ✓ {match_msg}")
                    result["overall_status"] = "PASSED"
                else:
                    print(f"  ✗ {match_msg}")
                    result["overall_status"] = "FAILED"
            else:
                result["overall_status"] = "PASSED"
        else:
            print(f"  ✗ Execution failed")
            print(f"    {exec_output[:200]}")
        
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
        check_students=args.check_stuid
    )
    
    try:
        tester.run_all_tests()
    finally:
        if args.cleanup:
            tester.cleanup()


if __name__ == "__main__":
    main()
