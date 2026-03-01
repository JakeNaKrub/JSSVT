import os
import sys
import zipfile
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Callable
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox, simpledialog

class JavaSubmissionTester:
    """
    Recursively process student Java submission zips and test them.
    This variant is tailored for *single‑file* assignments where each
    student folder contains exactly one archive.  The archive may include a
    mixture of `.java` source files and additional `.zip` archives; in that
    scenario each item should be considered an independent submission.

    Workflow:
    1. Discover every top‑level archive or raw source in the submissions tree
    2. For each student archive, split its contents into separate submissions
       (java files become their own entries; inner zips are left intact)
    3. Extract each submission to a uniquely numbered temporary directory
    4. Compile Java files (including default App.java)
    5. Execute and capture output
    6. Generate test report
    """
    
    def __init__(self, 
                 submissions_dir: str = "submissions",
                 default_code_dir: str = "default_code",
                 results_dir: str = "test_results",
                 expected_output: Optional[str] = None,
                 remove_packages: bool = False,
                 replace_main_file: bool = True,
                 normalize_filenames: bool = True,
                 check_students: Optional[List[str]] = None,
                 verbose: bool = False,
                 logger: Optional[Callable[[str], None]] = None,
                 stop_event: Optional[threading.Event] = None):
        """
        Initialize the Java submission tester.
        """
        self.submissions_dir = Path(submissions_dir)
        self.default_code_dir = Path(default_code_dir)
        self.results_dir = Path(results_dir)
        self.temp_extract_dir = Path("temp_extracts")
        self.expected_output = expected_output
        self.remove_packages = remove_packages
        self.replace_main_file = replace_main_file
        self.normalize_filenames = normalize_filenames
        self.check_students = check_students
        self.verbose = verbose
        self.logger = logger
        self.stop_event = stop_event
        
        # Create directories if they don't exist
        self.submissions_dir.mkdir(exist_ok=True, parents=True)
        self.default_code_dir.mkdir(exist_ok=True, parents=True)
        self.results_dir.mkdir(exist_ok=True, parents=True)
        self.temp_extract_dir.mkdir(exist_ok=True, parents=True)
        
        self.test_results = []
        # Detect the main class name from default_code_dir
        self.main_file_name = "App.java" # Default fallback
        java_files = list(self.default_code_dir.glob("*.java"))
        if java_files:
            # Picks the first .java file found in the default_code folder
            self.main_file_name = java_files[0].name
            
        self.main_class_name = self.main_file_name.replace(".java", "")
        self.log(f"✓ Detected main class from default_code: {self.main_class_name}")

    def log(self, message: str):
        """Helper to print to console and optional logger callback."""
        print(message)
        if self.logger:
            self.logger(message)

    def find_submissions(self) -> List[Tuple[str, Path]]:
        """
        Walk the submission directory tree and return a list of tuples in the
        form ``(student_id, path)`` where ``path`` is either a ``.zip`` archive
        or a standalone ``.java`` file.  Earlier versions only looked for zips
        which caused collisions when students uploaded individual source files
        (the LMS doesn't create separate folders for each upload).  Treating
        each file as its own submission makes grading deterministic and avoids
        name‑clashing problems.
        """
        submissions: List[Tuple[str, Path]] = []

        if not self.submissions_dir.exists():
            self.log(f"Error: Submission directory not found: {self.submissions_dir}")
            return []

        for student_folder in self.submissions_dir.iterdir():
            if not student_folder.is_dir():
                continue

            student_id = student_folder.name
            if self.check_students and student_id not in self.check_students:
                continue

            for zip_file in student_folder.glob("*.zip"):
                submissions.append((student_id, zip_file))
            for java_file in student_folder.glob("*.java"):
                submissions.append((student_id, java_file))

        self.log(f"Found {len(submissions)} submission files (zip/java)")
        return submissions
    
    # NOTE: the real ``extract_zip`` implementation is defined later in the
    # file (after the wrapper-explosion logic) and can handle both zips and
    # raw .java submissions.  The earlier version was accidentally retained
    # during refactoring and is therefore removed to avoid duplicate
    # definitions.
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
            
            # Filter 2: Skip macOS hidden metadata files
            if java_file.name.startswith("._"):
                continue
            
            # Filter 3: Skip .DS_Store
            if ".DS_Store" in java_file.name:
                continue
                
            java_files.append(java_file)
        return java_files
    
    def compile_java_files(self, work_dir: Path, java_files: List[Path]) -> Tuple[bool, str]:
        """
        Compile Java files using javac.
        Handles files nested in src/ folders or other subdirectories.
        """
        if not java_files:
            return False, "No Java files found"
        
        try:
            # Get relative paths from work_dir
            rel_files = [str(f.relative_to(work_dir)) for f in java_files]
            
            # Create output directory for compiled classes
            out_dir = work_dir / f"bin_{work_dir.name}"
            out_dir.mkdir(exist_ok=True)
            
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
        """
        try:
            bin_dir = work_dir / f"bin_{work_dir.name}"
            classpath = str(bin_dir) if bin_dir.exists() else str(work_dir)
            
            # Use detected main class name
            cmd = ["java", "-cp", classpath, self.main_class_name]
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
    def preprocess_nested_zips(self):
        """
        Scans all submission zips. If a zip acts as a 'wrapper' (contains other zips 
        but no Java files), it 'explodes' them into separate submission files.
        """
        self.log("Scanning and splitting student archives...")
        
        # We'll iterate over every submission entry; only zip files are relevant
        initial_subs = self.find_submissions()
        
        for student_id, zip_path in initial_subs:
            # only process archives here, raw java files will be handled later
            if zip_path.suffix.lower() != ".zip":
                continue
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    members = [m for m in zf.namelist() if not m.startswith("__MACOSX")]
                    for member in members:
                        if member.endswith(".java") or member.endswith(".zip"):
                            # extract the individual item
                            zf.extract(member, zip_path.parent)
                            extracted = zip_path.parent / member
                            dest_name = f"{student_id}_{Path(member).name}"
                            dest_path = zip_path.parent / dest_name
                            # remove existing collision if any
                            if dest_path.exists():
                                dest_path.unlink()
                            shutil.move(str(extracted), str(dest_path))
                            self.log(f"    ✓ Created separate submission: {dest_name}")
                # keep original archive out of future processing
                backup_name = zip_path.with_suffix(".zip.original")
                zip_path.rename(backup_name)
                self.log(f"    → Original moved to {backup_name.name}")
            except Exception as e:
                self.log(f"  ⚠ Error splitting {zip_path.name}: {e}")
    def extract_zip(self, zip_path: Path, student_id: str) -> Optional[Path]:
        """
        Extract a submission path into a unique folder.  Handles both zip
        archives and lone `.java` files (the latter are simply copied).
        """
        try:
            counter = 1
            while (self.temp_extract_dir / f"{student_id}_{counter}").exists():
                counter += 1
            
            extract_path = self.temp_extract_dir / f"{student_id}_{counter}"
            extract_path.mkdir(parents=True, exist_ok=True)
            
            if zip_path.suffix.lower() == ".zip":
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_path)
                self.flatten_extraction(extract_path)
            else:
                # stand-alone file – just copy into working dir
                try:
                    shutil.copy(zip_path, extract_path / zip_path.name)
                except Exception as e:
                    self.log(f"  ✗ Could not copy file {zip_path.name}: {e}")
                    return None
            
            self.log(f"  ✓ Extracted to unique folder: {extract_path.name}")
            return extract_path
        except Exception as e:
            self.log(f"  ✗ Failed to extract {zip_path}: {e}")
            return None
    def test_submission(self, student_id: str, submission_path: Path) -> Dict:
        self.log(f"\nTesting {student_id} ({submission_path.name})...")
        
        result = {
            "student_id": student_id,
            "submission": str(submission_path),
            "timestamp": datetime.now().isoformat(),
            "extraction": {"success": False},
            "compilation": {"success": False},
            "execution": {"success": False},
            "overall_status": "FAILED"
        }
        
        # Step 1: Extract submission
        extract_path = self.extract_zip(submission_path, student_id)
        if not extract_path:
            return result
        result["extraction"]["success"] = True

        # Step 2: Handle Packages (Optional feature)
        if self.remove_packages:
            for java_file in self.find_java_files(extract_path):
                try:
                    content = java_file.read_text(encoding='utf-8')
                    updated = re.sub(r'^\s*package\s+[\w.]+\s*;', '', content, flags=re.MULTILINE)
                    if updated != content:
                        java_file.write_text(updated, encoding='utf-8')
                except Exception as e:
                    self.log(f"  ⚠ Could not process {java_file.name}: {e}")

        # Step 3: DYNAMIC INJECTION
        # Find where the student's Java files actually are (handles nested folders/src folders)
        # Step 3: DYNAMIC INJECTION
        # Find where the student's Java files actually live in the new folder
        # Step 3: SMART DETECTION & INJECTION
        # Step 3: SMART DETECTION & INJECTION
        java_files = self.find_java_files(extract_path)
        default_main_path = self.default_code_dir / self.main_file_name
        
        if not default_main_path.exists():
            self.log(f"  ✗ Error: Master {self.main_file_name} not found in default_code")
            return result

        student_main_path = None
        
        if java_files:
            # A. First, try to find by Name Match
            target_dir = java_files[0].parent
            for f in java_files:
                if f.name == self.main_file_name:
                    student_main_path = f
                    break
            
            # B. If name doesn't match, search for 'public static void main' in contents
            if not student_main_path:
                for f in java_files:
                    try:
                        if "public static void main" in f.read_text(encoding='utf-8'):
                            student_main_path = f
                            self.log(f"  ℹ Found main method in differently named file: {f.name}")
                            break
                    except Exception:
                        continue

            # --- NEW: NORMALIZATION LOGIC ---
            # Fix files renamed by submission systems (e.g., A-111-2334344.java -> A111.java)
            if self.normalize_filenames and student_main_path and student_main_path.exists():
                try:
                    content = student_main_path.read_text(encoding='utf-8')
                    # Find the real class name inside the file
                    match = re.search(r'public\s+class\s+([a-zA-Z0-9_$]+)', content)
                    if match:
                        real_class_name = match.group(1)
                        correct_filename = f"{real_class_name}.java"
                        
                        if student_main_path.name != correct_filename:
                            new_path = student_main_path.parent / correct_filename
                            if new_path.exists(): 
                                new_path.unlink() 
                            student_main_path.rename(new_path)
                            self.log(f"  ✎ Normalized: {student_main_path.name} -> {correct_filename}")
                            student_main_path = new_path
                            self.main_class_name = real_class_name
                except Exception as e:
                    self.log(f"  ⚠ Normalization error: {e}")
            # --- END NORMALIZATION ---

        # Step 3.1: Decide whether to Replace, Execute, or Inject
        if student_main_path:
            if self.replace_main_file:
                # Force replace: overwrite student's file location with your master file
                shutil.copy(default_main_path, student_main_path.parent / self.main_file_name)
                # If the names were different (e.g., student used MyMain.java), delete their original
                if student_main_path.name != self.main_file_name:
                    student_main_path.unlink() 
                self.log(f"  ✓ Replaced student's {student_main_path.name} with master {self.main_file_name}")
                self.main_class_name = self.main_file_name.replace(".java", "")
            else:
                self.log(f"  ℹ Keeping and executing student's {student_main_path.name}")
                self.main_class_name = student_main_path.stem 
        else:
            # C. No main file found at all: Inject the master file
            target_dir = java_files[0].parent if java_files else extract_path
            shutil.copy(default_main_path, target_dir / self.main_file_name)
            self.log(f"  ⚠ No main entry point found; injected {self.main_file_name}")
            self.main_class_name = self.main_file_name.replace(".java", "")
        # Step 4: Final File List (Refresh to include the injected main class)
        java_files = self.find_java_files(extract_path)
        
        # Step 5: Compile
        compile_success, compile_output = self.compile_java_files(extract_path, java_files)
        result["compilation"]["success"] = compile_success
        result["compilation"]["output"] = compile_output
        
        if not compile_success:
            self.log(f"  ✗ Compilation failed")
            return result

        # Step 6: Execute
        exec_success, exec_output = self.run_app(extract_path)
        result["execution"]["success"] = exec_success
        result["execution"]["output"] = exec_output
        
        if exec_success:
            if self.expected_output:
                match, message = self.compare_output(exec_output, self.expected_output)
                result["output_validation"] = {"success": match, "message": message}
                result["overall_status"] = "PASSED" if match else "FAILED"
                self.log(f"  {'✓' if match else '✗'} Validation {'passed' if match else 'failed'}")
            else:
                result["overall_status"] = "PASSED"
                self.log(f"  ✓ Execution successful")
        else:
            self.log(f"  ✗ Execution failed")

        return result
    def run_all_tests(self) -> List[Dict]:
        """
        Find and test all student submissions.
        """
        self.log("=" * 60)
        self.log("Java Submission Tester Started")
        self.log("=" * 60)
        
        # 1. RUN THE EXPLODER FIRST
        self.preprocess_nested_zips()
        
        # 2. Re-scan directories (now that we might have created new zip files)
        submissions = self.find_submissions()
        
        if not submissions:
            self.log("No submission files found in submissions/student_id/ directories!")
            return []
        
        # Test each submission record (zip or raw file)
        for student_id, path in submissions:
            if self.stop_event and self.stop_event.is_set():
                self.log("\n!!! Grading Stopped by User !!!")
                break
                
            result = self.test_submission(student_id, path)
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
            self.log(f"✓ Results saved to: {output_file}")
        except Exception as e:
            self.log(f"Error saving results: {e}")
    
    def save_csv_report(self) -> None:
        """Save test results to CSV file."""
        import csv
        
        output_file = self.results_dir / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            # before writing we may need to deduplicate by student id
            filtered: List[Dict] = []
            seen: Dict[str, bool] = {}  # maps id -> whether pass already recorded
            for r in self.test_results:
                sid = r.get("student_id")
                if sid in seen:
                    # we have seen this student before
                    if seen[sid]:
                        # already have a pass, skip everything else
                        continue
                    else:
                        # previous entries all failures; if this one passed replace
                        if r.get("overall_status") == "PASSED":
                            filtered = [x for x in filtered if x.get("student_id") != sid]
                            filtered.append(r)
                            seen[sid] = True
                        else:
                            filtered.append(r)
                else:
                    filtered.append(r)
                    seen[sid] = (r.get("overall_status") == "PASSED")

            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Write header
                writer.writerow(["Student ID", "Status", "Remark"])
                
                # Write results
                for result in filtered:
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
            
            self.log(f"✓ CSV report saved to: {output_file}")
        except Exception as e:
            self.log(f"Error saving CSV report: {e}")
    def flatten_extraction(self, extract_path: Path):
        """
        If a student zipped a folder instead of files, this moves 
        everything up to the root of the extract_path.
        
        FIX: Renames the container first to prevent 'Destination already exists' 
        errors if the inner folder has the same name as the outer folder.
        """
        # Filter out system files
        items = [
            i for i in extract_path.iterdir() 
            if i.name not in ["__MACOSX", ".DS_Store"] and not i.name.startswith("._")
        ]
        
        # If there is exactly one directory and no files, move contents up
        if len(items) == 1 and items[0].is_dir():
            container_dir = items[0]
            self.log(f"  → Flattening nested folder: {container_dir.name}")
            
            # 1. Rename the container to a temporary name (e.g. "TEMP_UNWRAP")
            # This prevents naming conflicts if the inner file has the same name as the container
            temp_container = extract_path / "TEMP_UNWRAP_FOLDER"
            
            # Handle edge case if TEMP_UNWRAP_FOLDER somehow exists
            if temp_container.exists():
                shutil.rmtree(temp_container)
                
            container_dir.rename(temp_container)
            
            # 2. Move contents from the temporary container to the root
            for sub_item in temp_container.iterdir():
                # specific move logic to handle collisions if necessary, 
                # but usually move() handles basic file-to-dir moves fine now that name is free
                try:
                    shutil.move(str(sub_item), str(extract_path))
                except Exception as e:
                    self.log(f"    ⚠ Could not move {sub_item.name}: {e}")

            # 3. Delete the now-empty temporary container
            try:
                temp_container.rmdir()
            except:
                pass # If it's not empty for some reason, ignore
    def print_summary(self) -> None:
        """Print summary of test results."""
        passed = sum(1 for r in self.test_results if r["overall_status"] == "PASSED")
        failed = len(self.test_results) - passed
        
        self.log("\n" + "=" * 60)
        self.log("TEST SUMMARY")
        self.log("=" * 60)
        self.log(f"Total submissions: {len(self.test_results)}")
        self.log(f"Passed: {passed}")
        self.log(f"Failed: {failed}")
        self.log("")
        
        for result in self.test_results:
            status_icon = "✓" if result["overall_status"] == "PASSED" else "✗"
            self.log(f"{status_icon} {result['student_id']}: {result['overall_status']}")
    
    def cleanup(self) -> None:
        """Clean up temporary extraction directory."""
        try:
            if self.temp_extract_dir.exists():
                shutil.rmtree(self.temp_extract_dir)
            self.log("\n✓ Cleaned up temporary files")
        except Exception as e:
            self.log(f"Warning: Could not cleanup temp files: {e}")


# -------------------------------------------------------------------------
# GUI Implementation
# -------------------------------------------------------------------------

class GradingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Java Single-File Assignment Auto-Grader")
        self.root.geometry("700x750")
        
        # Styles
        style = ttk.Style()
        style.theme_use('clam')
        
        # Variables
        self.submissions_dir = tk.StringVar(value=os.path.abspath("submissions"))
        self.default_code_dir = tk.StringVar(value=os.path.abspath("default_code"))
        self.results_dir = tk.StringVar(value=os.path.abspath("test_results"))
        self.expected_output_file = tk.StringVar(value="")
        self.remove_packages = tk.BooleanVar(value=False)
        self.replace_main_file = tk.BooleanVar(value=True)
        self.normalize_filenames = tk.BooleanVar(value=True)
        self.verbose = tk.BooleanVar(value=True)
        self.cleanup = tk.BooleanVar(value=True)
        self.student_filter = tk.StringVar(value="")
        
        self.stop_event = None

        self.create_menu()
        self.create_widgets()

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # --- File Menu ---
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # --- Import Menu ---
        import_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Import", menu=import_menu)
        import_menu.add_command(label="Import Single Submission...", command=self.import_single_submission)
        import_menu.add_command(label="Batch Import (Zip)...", command=self.import_batch_zip)
        import_menu.add_command(label="Batch Import (Folder)...", command=self.import_batch_folder)

        # --- Clean Menu ---
        clean_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Clean", menu=clean_menu)
        clean_menu.add_command(label="Clean Submissions Folder", command=self.clean_submissions)
        clean_menu.add_command(label="Clean Results Folder", command=self.clean_results)
        clean_menu.add_separator()
        clean_menu.add_command(label="Clean Temp Files", command=self.clean_temp_folder)
        
        # --- Help Menu ---
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def show_about(self):
        messagebox.showinfo("About", "Java Assignment Auto-Grader\n\nMade by Akeprapu Dulyapurk")

    def import_single_submission(self):
        """Import a single submission file (zip or java) and ask for the Student ID."""
        file_path = filedialog.askopenfilename(
            title="Select Student Submission File",
            filetypes=[("Zip or Java files", "*.zip;*.java"), ("All files", "*.*")]
        )
        if not file_path: return
        
        target_dir = self.submissions_dir.get()
        if not self._ensure_dir(target_dir): return

        path = Path(file_path)
        # Heuristic: look for first number sequence > 4 digits
        match = re.search(r'(\d{5,})', path.stem)
        initial_id = match.group(1) if match else path.stem
        
        student_id = simpledialog.askstring(
            "Import Submission", 
            f"Enter Student ID for file:\n{path.name}", 
            initialvalue=initial_id,
            parent=self.root
        )
        
        if student_id:
            student_id = student_id.strip()
            self.append_log(f"\n--- Importing single file ---")
            if self._process_import(path, student_id, target_dir, "manual input"):
                 messagebox.showinfo("Import Complete", f"Imported {path.name} into folder {student_id}")
        else:
            self.append_log("Import cancelled.")

    def import_batch_zip(self):
        """Import a single zip file containing folders named by student IDs."""
        file_path = filedialog.askopenfilename(
            title="Select Batch Zip File",
            filetypes=[("Zip files", "*.zip"), ("All files", "*.*")]
        )
        if not file_path: return
        
        self.append_log(f"\n--- Processing Batch Zip: {os.path.basename(file_path)} ---")
        
        # Temp dir for extraction
        temp_batch_dir = Path("temp_extracts") / "batch_import"
        if temp_batch_dir.exists():
            shutil.rmtree(temp_batch_dir)
        temp_batch_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_batch_dir)
            
            self._process_batch_source(temp_batch_dir)
                
        except Exception as e:
            self.append_log(f"✗ Batch Import Error: {e}")
            messagebox.showerror("Error", str(e))
        finally:
            if temp_batch_dir.exists():
                shutil.rmtree(temp_batch_dir)

    def import_batch_folder(self):
        """Import a folder containing subfolders named by student IDs."""
        folder_path = filedialog.askdirectory(title="Select Batch Folder (containing student folders)")
        if not folder_path: return

        self.append_log(f"\n--- Processing Batch Folder: {os.path.basename(folder_path)} ---")
        try:
            self._process_batch_source(Path(folder_path))
        except Exception as e:
            self.append_log(f"✗ Batch Import Error: {e}")
            messagebox.showerror("Error", str(e))

    def _process_batch_source(self, work_dir: Path):
        """Internal logic to process a directory containing student folders."""
        target_dir = self.submissions_dir.get()
        if not self._ensure_dir(target_dir): return

        # --- INTELLIGENT UNWRAP LOGIC ---
        # 1. List all items in work dir
        all_items = list(work_dir.iterdir())
        
        # 2. Filter out system junk to find "real" content
        visible_items = [
            i for i in all_items 
            if not i.name.startswith(".") and "__MACOSX" not in i.name
        ]
        
        # 3. If there is exactly one folder and no other "real" files, descend
        # This handles the case where the batch source is a wrapper folder (e.g. "Assignment1")
        if len(visible_items) == 1 and visible_items[0].is_dir():
            work_dir = visible_items[0]
            self.append_log(f"Descended into root folder: {work_dir.name}")
            
        # --- PRE-SCAN: Identify Students ---
        found_items = []
        skipped_items = []
        
        for item in work_dir.iterdir():
             if item.name.startswith(".") or item.name.startswith("__"): continue
             if item.is_dir():
                 found_items.append(item.name)
             else:
                 skipped_items.append(item.name)
        
        found_items.sort()
        
        # Validation: If we found no folders, warn user
        if not found_items:
             msg = "No student folders found."
             if skipped_items:
                 msg += f"\nFound {len(skipped_items)} files (e.g., {skipped_items[0]}). Expected folders."
             messagebox.showwarning("Batch Import", msg)
             return

        # --- PRE-SCAN: Confirmation Dialog ---
        msg_header = f"Found {len(found_items)} student folders to import into:\n{target_dir}\n\nExamples:"
        
        # Limit display list if too long
        display_list = "\n".join(f"- {x}" for x in found_items[:10])
        if len(found_items) > 10:
            display_list += f"\n... and {len(found_items)-10} more."
            
        msg = f"{msg_header}\n{display_list}\n\nProceed with import?"
        
        if not messagebox.askyesno("Confirm Batch Import", msg):
            self.append_log("Batch import cancelled by user.")
            return

        # --- PROCESS ---
        count = 0
        for item in work_dir.iterdir():
            # Skip macOS metadata or hidden files
            if item.name.startswith(".") or item.name.startswith("__"):
                continue
            
            if item.is_dir():
                student_id = item.name
                
                # Create destination
                student_dest = Path(target_dir) / student_id
                student_dest.mkdir(parents=True, exist_ok=True)
                
                # Create zip
                dest_zip = student_dest / f"{student_id}_batch.zip"
                self._zip_folder(item, dest_zip)
                
                self.append_log(f"✓ Processed {student_id}")
                count += 1
        
        if count > 0:
            self.append_log(f"--- Batch Import Complete: {count} folders processed ---\n")
            messagebox.showinfo("Import Complete", f"Successfully processed {count} student folders.")
        else:
            self.append_log("--- Batch Import: No folders processed ---\n")

    def _zip_folder(self, source_path: Path, dest_zip: Path):
        """Helper to zip a directory content."""
        with zipfile.ZipFile(dest_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in source_path.rglob('*'):
                if file.is_file():
                    # Skip DS_Store and hidden files
                    if file.name == ".DS_Store" or file.name.startswith("._"):
                        continue
                    zf.write(file, file.relative_to(source_path))

    def clean_submissions(self):
        self._clean_folder(self.submissions_dir.get(), "Submissions")

    def clean_results(self):
        self._clean_folder(self.results_dir.get(), "Results")

    def clean_temp_folder(self):
        # Temp folder is usually deleted by the script logic, but this forces it
        temp_dir = "temp_extracts"
        if os.path.exists(temp_dir):
            if messagebox.askyesno("Confirm Clean", f"Are you sure you want to delete temporary files in:\n{os.path.abspath(temp_dir)}?"):
                try:
                    shutil.rmtree(temp_dir)
                    self.append_log(f"✓ Cleaned temp directory: {temp_dir}")
                    messagebox.showinfo("Success", "Temporary files cleaned.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to clean temp: {e}")
        else:
            messagebox.showinfo("Info", "Temp directory does not exist.")

    def _clean_folder(self, folder_path, name):
        """Helper to delete and recreate a folder with confirmation."""
        if not folder_path: return
        
        if not os.path.exists(folder_path):
            messagebox.showinfo("Info", f"{name} folder does not exist.")
            return

        # Double confirmation for safety
        if messagebox.askyesno("Confirm Delete", f"WARNING: This will DELETE ALL FILES in the {name} folder:\n\n{folder_path}\n\nAre you sure?"):
            try:
                shutil.rmtree(folder_path)
                os.makedirs(folder_path)
                self.append_log(f"✓ Cleaned (deleted and recreated) {name} folder.")
                messagebox.showinfo("Success", f"{name} folder has been emptied.")
            except Exception as e:
                self.append_log(f"✗ Failed to clean {name}: {e}")
                messagebox.showerror("Error", f"Could not clean folder: {e}")

    def _ensure_dir(self, path):
        if not os.path.exists(path):
            try:
                os.makedirs(path)
                return True
            except OSError as e:
                messagebox.showerror("Error", f"Could not create folder: {e}")
                return False
        return True

    def _process_import(self, path: Path, student_id: str, target_dir: str, reason: str) -> bool:
        """Helper to copy file to student folder."""
        try:
            student_folder = os.path.join(target_dir, student_id)
            os.makedirs(student_folder, exist_ok=True)
            
            dest_path = os.path.join(student_folder, path.name)
            shutil.copy2(path, dest_path)
            self.append_log(f"✓ Imported {path.name} -> {student_id}/ ({reason})")
            return True
        except Exception as e:
            self.append_log(f"✗ Failed to import {path.name}: {e}")
            return False

    def create_widgets(self):
        # --- File Selection Frame ---
        file_frame = ttk.LabelFrame(self.root, text="Configuration", padding="10")
        file_frame.pack(fill="x", padx=10, pady=5)
        
        self.create_file_input(file_frame, "Submissions Folder:", self.submissions_dir, True, 0)
        self.create_file_input(file_frame, "Default Code Folder:", self.default_code_dir, True, 1)
        self.create_file_input(file_frame, "Results Folder:", self.results_dir, True, 2)
        self.create_file_input(file_frame, "Expected Output (Optional):", self.expected_output_file, False, 3)

        # --- Options Frame ---
        opt_frame = ttk.LabelFrame(self.root, text="Options", padding="10")
        opt_frame.pack(fill="x", padx=10, pady=5)
        
        # Row 0
        ttk.Checkbutton(opt_frame, text="Remove Package Declarations", variable=self.remove_packages).grid(row=0, column=0, sticky="w", padx=5)
        ttk.Checkbutton(opt_frame, text="Cleanup Temp Files", variable=self.cleanup).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Checkbutton(opt_frame, text="Verbose Logging", variable=self.verbose).grid(row=0, column=2, sticky="w", padx=5)
        
        # Row 1
        ttk.Checkbutton(opt_frame, text="Replace Student Main Class", variable=self.replace_main_file).grid(row=1, column=0, sticky="w", padx=5, pady=(5,0))
        ttk.Checkbutton(opt_frame, text="Normalize Filenames", variable=self.normalize_filenames).grid(row=1, column=1, sticky="w", padx=5, pady=(5,0))
        
        # Row 2 (Filter)
        ttk.Label(opt_frame, text="Filter Students (space separated):").grid(row=2, column=0, sticky="w", padx=5, pady=(10,0))
        ttk.Entry(opt_frame, textvariable=self.student_filter, width=40).grid(row=2, column=1, columnspan=2, sticky="we", padx=5, pady=(10,0))
        # --- Action Frame ---
        act_frame = ttk.Frame(self.root, padding="10")
        act_frame.pack(fill="x", padx=10)
        
        self.start_btn = ttk.Button(act_frame, text="START GRADING", command=self.start_grading_thread)
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=5)
        
        self.stop_btn = ttk.Button(act_frame, text="STOP", command=self.stop_grading, state="disabled")
        self.stop_btn.pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=5)

        # --- Output Log ---
        log_frame = ttk.LabelFrame(self.root, text="Execution Log", padding="5")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

        # Tag configuration for log colors
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("SUCCESS", foreground="green")

    def create_file_input(self, parent, label_text, variable, is_dir, row):
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="we", padx=5, pady=5)
        
        cmd = self.browse_dir if is_dir else self.browse_file
        ttk.Button(parent, text="Browse", command=lambda: cmd(variable)).grid(row=row, column=2, padx=5, pady=5)
        parent.columnconfigure(1, weight=1)

    def browse_dir(self, var):
        path = filedialog.askdirectory(initialdir=var.get())
        if path: var.set(path)

    def browse_file(self, var):
        path = filedialog.askopenfilename(initialdir=os.path.dirname(var.get() or "."))
        if path: var.set(path)

    def append_log(self, message):
        """Thread-safe logging to the text widget"""
        def _update():
            self.log_text.config(state='normal')
            
            tag = None
            if "✗" in message or "Error" in message or "FAILED" in message:
                tag = "ERROR"
            elif "✓" in message or "PASSED" in message:
                tag = "SUCCESS"
                
            self.log_text.insert(tk.END, message + "\n", tag)
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
        
        self.root.after(0, _update)

    def start_grading_thread(self):
        # validate
        if not os.path.isdir(self.submissions_dir.get()):
            messagebox.showerror("Error", "Submissions directory does not exist.")
            return

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')

        self.stop_event = threading.Event()
        thread = threading.Thread(target=self.run_logic, daemon=True)
        thread.start()

    def stop_grading(self):
        if self.stop_event:
            self.stop_event.set()
            self.append_log("Stopping...")
            self.stop_btn.config(state="disabled")

    def run_logic(self):
        try:
            expected_content = None
            if self.expected_output_file.get() and os.path.exists(self.expected_output_file.get()):
                try:
                    with open(self.expected_output_file.get(), 'r') as f:
                        expected_content = f.read()
                except Exception as e:
                    self.append_log(f"Error reading expected output: {e}")

            check_ids = self.student_filter.get().strip().split()
            if not check_ids: check_ids = None

            tester = JavaSubmissionTester(
                submissions_dir=self.submissions_dir.get(),
                default_code_dir=self.default_code_dir.get(),
                results_dir=self.results_dir.get(),
                expected_output=expected_content,
                remove_packages=self.remove_packages.get(),
                replace_main_file=self.replace_main_file.get(),
                normalize_filenames=self.normalize_filenames.get(),
                check_students=check_ids,
                verbose=self.verbose.get(),
                logger=self.append_log,  # Pass the GUI logging function
                stop_event=self.stop_event
            )

            tester.run_all_tests()
            
            if self.cleanup.get():
                tester.cleanup()
                
            if not self.stop_event.is_set():
                self.append_log("\n--- Grading Complete ---")
            
        except Exception as e:
            self.append_log(f"\nCRITICAL ERROR: {str(e)}")
        finally:
            def _reset_btns():
                self.start_btn.config(state="normal")
                self.stop_btn.config(state="disabled")
            self.root.after(0, _reset_btns)

def main():
    """Main entry point. Switch between GUI and CLI based on arguments."""
    import argparse
    
    # Check if arguments are passed. If only the script name is present, or explicit --gui flag, run GUI
    if len(sys.argv) == 1 or "--gui" in sys.argv:
        root = tk.Tk()
        app = GradingGUI(root)
        root.mainloop()
        return

    # CLI Logic
    parser = argparse.ArgumentParser(
        description="Test Java submissions from student zip files"
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the Graphical User Interface"
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
        "--no-replace-main",
        action="store_true", 
        help="Do not replace student main file")
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
    parser.add_argument("--no-normalize",
                        action="store_false", 
                        dest="normalize", 
                        help="Disable filename normalization")
    parser.set_defaults(normalize=True)
    
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
        replace_main_file=not args.no_replace_main,
        normalize_filenames=args.normalize,
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
