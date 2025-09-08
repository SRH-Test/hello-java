#!/usr/bin/env python3
"""
Polaris Default Branch Setter

This script automatically sets the default branch in Polaris based on the current
GitHub branch being scanned. It should be run after a Polaris scan completes.

Environment Variables Required:
- POLARIS_SERVER_URL: The Polaris server URL
- POLARIS_ACCESS_TOKEN: Your Polaris access token
- GITHUB_REF: GitHub reference (e.g., refs/heads/main)
- GITHUB_REPOSITORY: Repository name (e.g., owner/repo-name)

Usage:
    python polaris_branch_setter.py
"""

import os
import sys
import requests
import json
import time
from typing import Optional, Dict, Any
from urllib.parse import urljoin


class PolarisAPI:
    def __init__(self, server_url: str, access_token: str, org_id: str = None):
        self.server_url = server_url.rstrip('/')
        self.access_token = access_token
        self.org_id = org_id
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        if org_id:
            self.session.headers['organization-id'] = org_id

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a request to the Polaris API with error handling."""
        url = urljoin(self.server_url + '/', endpoint.lstrip('/'))
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            raise

    def find_project_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Find a project by its name."""
        print(f"Searching for project: {project_name}")
        
        # Search across all portfolios for the project
        try:
            response = self._make_request(
                'GET', 
                '/api/projects',
                params={'_filter': f'name=="{project_name}"', '_limit': 10}
            )
            
            projects = response.json().get('_items', [])
            
            if not projects:
                print(f"No project found with name: {project_name}")
                return None
            
            if len(projects) > 1:
                print(f"Warning: Multiple projects found with name '{project_name}'. Using the first one.")
            
            project = projects[0]
            print(f"Found project: {project['name']} (ID: {project['id']})")
            return project
            
        except Exception as e:
            print(f"Error searching for project: {e}")
            return None

    def get_project_branches(self, portfolio_id: str, application_id: str, project_id: str) -> list:
        """Get all branches for a project."""
        try:
            endpoint = f'/api/portfolios/{portfolio_id}/applications/{application_id}/projects/{project_id}/branches'
            response = self._make_request('GET', endpoint)
            return response.json().get('_items', [])
        except Exception as e:
            print(f"Error getting project branches: {e}")
            return []

    def find_branch_by_name(self, portfolio_id: str, application_id: str, project_id: str, branch_name: str) -> Optional[Dict[str, Any]]:
        """Find a specific branch by name."""
        branches = self.get_project_branches(portfolio_id, application_id, project_id)
        
        for branch in branches:
            if branch['name'] == branch_name:
                return branch
        
        print(f"Branch '{branch_name}' not found in project")
        return None

    def set_default_branch(self, portfolio_id: str, application_id: str, project_id: str, branch_id: str, branch_name: str) -> bool:
        """Set a branch as the default branch for a project."""
        try:
            endpoint = f'/api/portfolios/{portfolio_id}/applications/{application_id}/projects/{project_id}/branches/{branch_id}'
            
            # Get current branch data first
            response = self._make_request('GET', endpoint)
            branch_data = response.json()
            
            # Update to set as default
            branch_data['isDefault'] = True
            
            # Remove fields that shouldn't be in the PATCH request
            for field in ['_links', 'id']:
                branch_data.pop(field, None)
            
            # Make PATCH request to update branch
            headers = {
                'Content-Type': 'application/vnd.polaris.portfolios.branches-1+json'
            }
            
            response = self._make_request(
                'PATCH', 
                endpoint, 
                json=branch_data,
                headers=headers
            )
            
            print(f"Successfully set '{branch_name}' as default branch")
            return True
            
        except Exception as e:
            print(f"Error setting default branch: {e}")
            return False


def get_github_branch_name() -> str:
    """Extract branch name from GitHub environment variables."""
    github_ref = os.getenv('GITHUB_REF', '')
    
    if github_ref.startswith('refs/heads/'):
        return github_ref.replace('refs/heads/', '')
    elif github_ref.startswith('refs/pull/'):
        # For pull requests, use the base branch
        return os.getenv('GITHUB_BASE_REF', 'main')
    else:
        # Fallback to main if we can't determine the branch
        print(f"Warning: Could not determine branch from GITHUB_REF: {github_ref}")
        return 'main'


def get_polaris_application_name() -> str:
    """Generate the Polaris application name based on repository name."""
    repo_name = os.getenv('GITHUB_REPOSITORY', '').split('/')[-1]
    if not repo_name:
        raise ValueError("GITHUB_REPOSITORY environment variable not found")
    
    return f"SRH-{repo_name}"


def wait_for_scan_completion(api: PolarisAPI, project_data: Dict[str, Any], branch_name: str, max_wait_minutes: int = 30) -> bool:
    """Wait for the Polaris scan to complete before setting default branch."""
    print(f"Waiting for scan completion on branch '{branch_name}'...")
    
    portfolio_id = project_data.get('portfolioId')
    application_id = project_data.get('applicationId') 
    project_id = project_data.get('id')
    
    if not all([portfolio_id, application_id, project_id]):
        print("Missing required project identifiers")
        return False
    
    max_attempts = max_wait_minutes * 2  # Check every 30 seconds
    
    for attempt in range(max_attempts):
        branch = api.find_branch_by_name(portfolio_id, application_id, project_id, branch_name)
        
        if branch:
            print(f"Branch '{branch_name}' found, scan appears to be complete")
            return True
        
        if attempt < max_attempts - 1:
            print(f"Branch not found yet, waiting 30 seconds... (attempt {attempt + 1}/{max_attempts})")
            time.sleep(30)
    
    print(f"Timeout waiting for branch '{branch_name}' to appear")
    return False


def main():
    """Main function to set the default branch in Polaris."""
    # Get required environment variables
    polaris_server_url = os.getenv('POLARIS_SERVER_URL')
    polaris_access_token = os.getenv('POLARIS_ACCESS_TOKEN')
    org_id = os.getenv('POLARIS_ORGANIZATION_ID')  # Optional
    
    if not polaris_server_url or not polaris_access_token:
        print("Error: POLARIS_SERVER_URL and POLARIS_ACCESS_TOKEN environment variables are required")
        sys.exit(1)
    
    # Get GitHub information
    try:
        branch_name = get_github_branch_name()
        application_name = get_polaris_application_name()
    except Exception as e:
        print(f"Error getting GitHub information: {e}")
        sys.exit(1)
    
    print(f"Branch name: {branch_name}")
    print(f"Application name: {application_name}")
    
    # Initialize Polaris API client
    api = PolarisAPI(polaris_server_url, polaris_access_token, org_id)
    
    # Find the project
    project_data = api.find_project_by_name(application_name)
    if not project_data:
        print(f"Could not find project '{application_name}' in Polaris")
        sys.exit(1)
    
    # Extract project information
    portfolio_id = project_data.get('portfolioId')
    application_id = project_data.get('applicationId')
    project_id = project_data.get('id')
    
    if not all([portfolio_id, application_id, project_id]):
        print("Error: Could not extract required project identifiers")
        sys.exit(1)
    
    # Wait for scan to complete
    if not wait_for_scan_completion(api, project_data, branch_name):
        print("Scan did not complete in time, exiting")
        sys.exit(1)
    
    # Find the specific branch
    branch = api.find_branch_by_name(portfolio_id, application_id, project_id, branch_name)
    if not branch:
        print(f"Branch '{branch_name}' not found in project '{application_name}'")
        sys.exit(1)
    
    # Check if it's already the default
    if branch.get('isDefault', False):
        print(f"Branch '{branch_name}' is already the default branch")
        sys.exit(0)
    
    # Set as default branch
    success = api.set_default_branch(
        portfolio_id, 
        application_id, 
        project_id, 
        branch['id'], 
        branch_name
    )
    
    if success:
        print(f"Successfully set '{branch_name}' as the default branch for '{application_name}'")
        sys.exit(0)
    else:
        print("Failed to set default branch")
        sys.exit(1)


if __name__ == "__main__":
    main()
