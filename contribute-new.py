"""
This is a python script designed to help you to submit files, manage tags and stuff.
This requires:

Requires: git, GitHub CLI (gh), Python 3 with tkinter (all default on Windows).
Usage:  py contribute-new.py

"""

import sys
import json
import re 
import shutil
import subprocess
import os

from pathlib import Path

try:
    import questionary
except ImportError:
    print ("\n\nYou must install questionary this program to work!\nPlease run: python -m pip install questionary\n\n")
    sys.exit(1)

print("Testing 123")

ROOT           = Path(__file__).resolve().parent
CONTENT_DIR    = ROOT / "public" / "content"
INDEX_FILE     = ROOT / "public" / "index.json"
TAG_OVERRIDES  = ROOT / "public" / "tag-overrides.json"
META_OVERRIDES = ROOT / "public" / "metadata-overrides.json"

STUB_PREFIX   = "(external)-"
STUB_SUFFIX   = ".txt"

UPSTREAM_REPO   = "sulavtpa/itc-index"
UPSTREAM_BRANCH = "main"

def run(command):
    templist = []
    for i in command:
        templist.append(str(i))
    return subprocess.run(
        templist,
        cwd = ROOT,
        capture_output = True,
        text = True,
        encoding = "utf-8",
        errors = "replace"
    )

# def test_run():
#     print(run(["git", "status"]))
# test_run()

# Making a function to run git and gh (Github CLI) commands
def git(command):
    templist = run("git" + command)
    if templist.returncode != 0:
        print("\n\ngit is not installed or not working properly!\n\n")
        sys.exit(1)

def gh(command):
    templist = run("gh" + command)
    if templist.returncode != 0:
        print("\n\ngh is not installed or not working properly!\n\n")
        sys.exit(1)

# Initial Checks to make sure computer has everything setup correctly
def initial_checks():
    
    # Clear the screen first
    os.system('cls' if os.name == 'nt' else 'clear')

    # Check for git
    commandoutput = run(["git", "--version"])
    if commandoutput.returncode != 0:
        print("\n\ngit is not installed or not working properly!\n\n")
        sys.exit(1)

    # Check for gh
    commandoutput= run(["gh", "--version"])
    if commandoutput.returncode != 0:
        print("GitHub CLI is not installed, download link: https://cli.github.com")
        sys.exit(1)

    # Check if the user has email, username setup on git
    commandoutput_name  = run(["git", "config", "user.name"]).stdout.strip()
    commandoutput_email = run(["git", "config", "user.email"]).stdout.strip()
    if not commandoutput_name or not commandoutput_email:
        print("Your git name/email are not set. Run these two commands once:")
        print('    git config --global user.name  "Your Name"')
        print('    git config --global user.email "you@example.com"')
        sys.exit(1)

    # Github CLI logged in?
    auth = run(["gh", "auth", "status"])
    output = auth.stdout + auth.stderr
    if auth.returncode != 0:
        print("You are not logged in to GitHub. Run this once:")
        print("    gh auth login")
        sys.exit(1)