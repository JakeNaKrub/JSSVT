#!/usr/bin/env python3
"""
Setup script for Java Submission Tester
Creates directory structure and template files
"""

import os
from pathlib import Path


def create_directories():
    """Create required directories."""
    dirs = [
        "submissions",
        "default_code",
        "test_results",
        "temp_extracts"
    ]
    
    for dir_name in dirs:
        path = Path(dir_name)
        path.mkdir(exist_ok=True)
        print(f"✓ Created directory: {dir_name}/")


def create_default_app():
    """Create template App.java in default_code."""
    app_java = Path("default_code") / "App.java"
    
    if app_java.exists():
        print(f"⚠ {app_java} already exists, skipping...")
        return
    
    template = """public class App {
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
"""
    
    with open(app_java, 'w') as f:
        f.write(template)
    
    print(f"✓ Created: {app_java}")


def create_expected_output():
    """Create template expected_output.txt."""
    output_file = Path("expected_output.txt")
    
    if output_file.exists():
        print(f"⚠ {output_file} already exists, skipping...")
        return
    
    template = """Name: Barbie1
Material: Plastic
Price: $29.99
Barbie sings: I'm a Barbie girl in a Barbie world!

Name: Barbie2
Material: Plastic
Price: $34.99
Barbie sings: I'm a Barbie girl in a Barbie world!

Name: Teddy
Material: Fur
Price: $19.99
Teddy Doll says: Hug me!

Name: Porcelain1
Material: Porcelain
Price: $49.99
This doll is fragile. Not playing with it.

Name: Porcelain2
Material: Porcelain
Price: $59.99
This doll is fragile. Not playing with it.
"""
    
    with open(output_file, 'w') as f:
        f.write(template)
    
    print(f"✓ Created: {output_file}")


def create_example_student_folder():
    """Create example student folder structure."""
    example_dir = Path("submissions") / "student_example"
    example_dir.mkdir(exist_ok=True)
    
    readme = example_dir / "README.txt"
    if not readme.exists():
        with open(readme, 'w') as f:
            f.write("""INSTRUCTIONS:
1. Create a folder for each student using their Student ID
   Example: submissions/6838205621/

2. Place the student's submission zip file inside
   Example: submissions/6838205621/submission.zip

3. The zip file should contain:
   - Doll.java (base class)
   - Barbie.java (subclass)
   - TeddyDoll.java (subclass)
   - PorcelainDoll.java (subclass)

4. Each submission can have these in:
   - Root directory, OR
   - src/ subdirectory, OR
   - Any nested folder structure

Example structure:
submissions/
├── 6838205621/
│   └── submission.zip
│       ├── Doll.java
│       ├── Barbie.java
│       ├── TeddyDoll.java
│       └── PorcelainDoll.java
├── 6838205622/
│   └── homework.zip
│       └── src/
│           ├── Doll.java
│           ├── Barbie.java
│           ├── TeddyDoll.java
│           └── PorcelainDoll.java
└── 6838205623/
    └── lab02.zip
        └── Lab02/
            ├── Doll.java
            ├── Barbie.java
            ├── TeddyDoll.java
            └── PorcelainDoll.java
""")
        print(f"✓ Created: {readme}")
    else:
        print(f"⚠ {readme} already exists, skipping...")


def create_gitignore():
    """Create .gitignore file."""
    gitignore = Path(".gitignore")
    
    if gitignore.exists():
        print(f"⚠ {gitignore} already exists, skipping...")
        return
    
    content = """# Directories
temp_extracts/
test_results/
submissions/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
"""
    
    with open(gitignore, 'w') as f:
        f.write(content)
    
    print(f"✓ Created: {gitignore}")


def print_next_steps():
    """Print instructions for next steps."""
    print("\n" + "=" * 60)
    print("SETUP COMPLETE!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Place student submissions in: submissions/student_id/submission.zip")
    print("2. Edit default_code/App.java if needed (template provided)")
    print("3. Edit expected_output.txt to match your expected output (optional)")
    print("\nRun tests with:")
    print("  python java_submission_tester.py")
    print("\nWith options:")
    print("  python java_submission_tester.py --remove-pack --cleanup")
    print("  python java_submission_tester.py --check-stuid 6838205621 6838205622")
    print("  python java_submission_tester.py --expected expected_output.txt")
    print("\nFor more help:")
    print("  python java_submission_tester.py --help")
    print("=" * 60 + "\n")


def main():
    """Run setup."""
    print("=" * 60)
    print("Java Submission Tester - Setup")
    print("=" * 60 + "\n")
    
    create_directories()
    print()
    
    create_default_app()
    create_expected_output()
    print()
    
    create_example_student_folder()
    create_gitignore()
    print()
    
    print_next_steps()


if __name__ == "__main__":
    main()
