#!/usr/bin/env python3
"""
Script to add students to specific Gitea repositories based on email addresses in group.txt.

This script leverages the Joint Teapot framework to:
1. Read email addresses from group.txt file
2. Add students as collaborators to GitWksp_teamXX repositories based on line number
3. Use the underlying Gitea API for repository management
"""
import sys
from typing import List
from joint_teapot.teapot import Teapot
from giteahelper import create_teams_and_repos

def get_username_from_email(emails: List[str]) -> List[str]:
    usernames = []
    for email in emails:
        # Add @sjtu.edu.cn to account names to turn them into email addresses
        email = email.strip()
        if "@" not in email:
            # This is an account name, add the domain to make it an email
            email = email + "@sjtu.edu.cn"

        if not email.endswith("@sjtu.edu.cn"):
            print(f"Warning: Email {email} is not an SJTU email address")
            continue
        username = email.split("@")[0]
        usernames.append(username)
        print(f"username extracted: {username}")
    return usernames


def add_students_from_group_file(teapot: Teapot, group_file: str, template_repo:str,confirm:bool=False) -> None:
    """
    Add students to repositories by reading email addresses from group.txt file.
    Each line creates a team repository named GitWksp_teamXX where XX is the line number.

    Args:
        teapot: The initialized Teapot instance
        group_file: Path to the group.txt file containing space-separated email addresses
        template_repo: The template repository name to use for creating new repositories
        confirm: If True, ask for user confirmation before creating each repository
    """
    try:
        with open(group_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        print(f"Processing {len(lines)} groups from {group_file}")

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Create repository name with group ID (line number)
            repo_name = f"GitWksp_team{i+1:02d}"  # GitWksp_team01, GitWksp_team02, etc.

            # Split the line by spaces to get email addresses
            emails = line.split()
            usernames = get_username_from_email(emails)
            print(f"Group {i+1}: Processing emails - {usernames} -> {repo_name}\n")
            if confirm:
                user_input = input("Proceed? (y/n): ")
                if user_input.lower() != 'y':
                    print("Operation cancelled by user.\n")
                    continue
            try:
                success = create_teams_and_repos(
                    teapot.gitea,
                    repo_name,
                    usernames,
                    template=template_repo
                )
            except Exception as e:
                print(f"Error creating repository {repo_name}: {e}\n")
                continue
            if not success:
                print(f"Failed to create repository {repo_name}\n")
                continue
            else:
                print(f"Repository {repo_name} created successfully\n")

        print(f"Completed processing {group_file}\n")

    except FileNotFoundError:
        print(f"Error: {group_file} not found\n")
    except Exception as e:
        print(f"Error processing {group_file}: {e}\n")


def main():
    """
    Main function to add students from group.txt to GitWksp_teamXX repositories.
    """
    confirm=False
    if sys.argv[1] == '-c' or sys.argv[1] == '--confirm':
        confirm=True
    print("Initializing Joint Teapot...\n")
    teapot = Teapot()

    print(f"--- Adding students from group.txt to GitWksp_teamXX repositories ---\n")
    print(f"Using organization: {teapot.gitea.org_name}\n")
    if confirm:
        user_input = input("Proceed? (y/n): ")
        if user_input.lower() != 'y':
            print("Operation cancelled by user.\n")
            return
    # Add students from group.txt to the GitWksp_teamXX repositories
    add_students_from_group_file(teapot, "group.txt", "template-Git-wksp-26Fa",confirm)

    print("Script completed!\n")


if __name__ == "__main__":
    main()
