#!/usr/bin/env python3
"""
Polaris Default Branch Setter

This script automatically sets the default branch in Polaris based on the
polaris_branch_name specified in the GitHub Actions workflow.

Environment Variables Required:
- POLARIS_SERVER_URL: The Polaris server URL
- POLARIS_ACCESS_TOKEN: Your Polaris access token
- POLARIS_APPLICATION_NAME: The application name (e.g., SRH-hello-java)
- POLARIS_PROJECT_NAME: The project name (e.g., hello-java)
- POLARIS_BRANCH_NAME: The branch name to set as default (e.g., new)

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
    def __init__(self, server_url: str, access_token: str):
        self.server_url = server_url.rstrip('/')
        self.access_token = access_token
        
        print(f"Initialized Polaris API client")
        print(f"Server: {self.server_url}")

    def _get_headers(self, extra_headers: Dict[str, str] = None) -> Dict[str, str]:
        """Get headers for API requests."""
        headers = {
            'Api-Token': self.access_token,
            'Accept': 'application/json'
        }
        
        if extra_headers:
            headers.update(extra_headers)
            
        return headers

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a request to the Polaris API with error handling."""
        url = urljoin(self.server_url + '/', endpoint.lstrip('/'))
        
        # Get headers for this request
        extra_headers = kwargs.pop('headers', {})
        headers = self._get_headers(extra_headers)
        
        print(f"Making {method} request to: {url}")
        print(f"Headers: {headers}")
        
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            print(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Response headers: {dict(response.headers)}")
                print(f"Response text: {response.text}")
            
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response headers: {dict(e.response.headers)}")
                print(f"Response text: {e.response.text}")
            raise

    def find_project_by_name(self, application_name: str, project_name: str) -> Optional[Dict[str, Any]]:
        """Find a project by application and project name."""
        print(f"Searching for project: {project_name} in application: {application_name}")
        
        try:
            # First, find all portfolios
            response = self._make_request('GET', '/api/portfolios')
            portfolios = response.json().get('_items', [])
            
            for portfolio in portfolios:
                portfolio_id = portfolio['id']
                print(f"Checking portfolio: {portfolio.get('name', 'Unknown')} (ID: {portfolio_id})")
                
                # Search for applications in this portfolio
                try:
                    app_response = self._make_request(
                        'GET', 
                        f'/api/portfolios/{portfolio_id}/applications',
                        params={'_filter': f'name=="{application_name}"', '_limit': 10}
                    )
                    
                    applications = app_response.json().get('_items', [])
                    
                    for application in applications:
                        application_id = application['id']
                        print(f"Found application: {application['name']} (ID: {application_id})")
                        
                        # Search for projects in this application
                        try:
                            project_response = self._make_request(
                                'GET',
                                f'/api/portfolios/{portfolio_id}/applications/{application_id}/projects',
                                params={'_filter': f'name=="{project_name}"', '_limit': 10}
                            )
                            
                            projects = project_response.json().get('_items', [])
                            
                            for project in projects:
                                print(f"Found project: {project['name']} (ID: {project['id']})")
                                # Add the IDs we need for API calls
                                project['portfolioId'] = portfolio_id
                                project['applicationId'] = application_id
                                return project
                                
                        except Exception as e:
                            print(f"Error searching projects in application {application_id}: {e}")
                            continue
                            
                except Exception as e:
                    print(f"Error searching applications in portfolio {portfolio_id}: {e}")
                    continue
            
            print(f"No project found with name '{project_name}' in application '{application_name}'")
            return None
            
        except Exception as e:
            print(f"Error searching for project: {e}")
            return None

    def get_project_branches(self, portfolio_id: str, application_id: str, project_id: str) -> list:
        """Get all branches for a project."""
        try:
            endpoint = f'/api/portfolios/{portfolio_id}/applications/{application_id}/projects/{project_id}/branches'
            response = self._make_request('GET', endpoint, params={'_limit': 100})
            return response.json().get('_items', [])
        except Exception as e:
            print(f"Error getting project branches: {e}")
            return []

    def find_branch_by_name(self, portfolio_id: str, application_id: str, project_id: str, branch_name: str) -> Optional[Dict[str, Any]]:
        """Find a specific branch by name."""
        branches = self.get_project_branches(portfolio_id, application_id, project_id)
        
        print(f"Available branches: {[branch['name'] for branch in branches]}")
        
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
            
            # Create the payload matching your working curl command
            patch_payload = {
                "name": branch_data.get("name", branch_name),
                "description": branch_data.get("description", ""),
                "source": branch_data.get("source", "CI"),
                "isDefault": True,
                "autoDeleteSetting": branch_data.get("autoDeleteSetting", False),
                "autoDeleteSettingsCustomized": branch_data.get("autoDeleteSettingsCustomized", False),
                "branchRetentionPeriodSetting": branch_data.get("branchRetentionPeriodSetting", 0)
            }
            
            # Add labelIds if present in the original data
            if "labelIds" in branch_data:
                patch_payload["labelIds"] = branch_data["labelIds"]
            
            print(f"PATCH payload: {json.dumps(patch_payload, indent=2)}")
            
            # Make PATCH request to update branch with correct headers
            patch_headers = {
                'Accept': 'application/vnd.polaris.portfolios.branches-1+json',
                'Content-Type': 'application/vnd.polaris.portfolios.branches-1+json'
            }
            
            response = self._make_request(
                'PATCH', 
                endpoint, 
                json=patch_payload,
                headers=patch_headers
            )
            
            print(f"Successfully set '{branch_name}' as default branch")
            return True
            
        except Exception as e:
            print(f"Error setting default branch: {e}")
            return False


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
    polaris_application_name = os.getenv('POLARIS_APPLICATION_NAME')
    polaris_project_name = os.getenv('POLARIS_PROJECT_NAME')
    polaris_branch_name = os.getenv('POLARIS_BRANCH_NAME')
    
    if not all([polaris_server_url, polaris_access_token, polaris_application_name, polaris_project_name, polaris_branch_name]):
        print("Error: Missing required environment variables:")
        print("- POLARIS_SERVER_URL")
        print("- POLARIS_ACCESS_TOKEN") 
        print("- POLARIS_APPLICATION_NAME")
        print("- POLARIS_PROJECT_NAME")
        print("- POLARIS_BRANCH_NAME")
        sys.exit(1)
    
    print(f"Application name: {polaris_application_name}")
    print(f"Project name: {polaris_project_name}")
    print(f"Branch name: {polaris_branch_name}")
    
    # Initialize Polaris API client
    api = PolarisAPI(polaris_server_url, polaris_access_token)
    
    # Find the project
    project_data = api.find_project_by_name(polaris_application_name, polaris_project_name)
    if not project_data:
        print(f"Could not find project '{polaris_project_name}' in application '{polaris_application_name}'")
        sys.exit(1)
    
    # Extract project information
    portfolio_id = project_data.get('portfolioId')
    application_id = project_data.get('applicationId')
    project_id = project_data.get('id')
    
    if not all([portfolio_id, application_id, project_id]):
        print("Error: Could not extract required project identifiers")
        sys.exit(1)
    
    # Wait for scan to complete
    if not wait_for_scan_completion(api, project_data, polaris_branch_name):
        print("Scan did not complete in time, exiting")
        sys.exit(1)
    
    # Find the specific branch
    branch = api.find_branch_by_name(portfolio_id, application_id, project_id, polaris_branch_name)
    if not branch:
        print(f"Branch '{polaris_branch_name}' not found in project '{polaris_project_name}'")
        sys.exit(1)
    
    # Check if it's already the default
    if branch.get('isDefault', False):
        print(f"Branch '{polaris_branch_name}' is already the default branch")
        sys.exit(0)
    
    # Set as default branch
    success = api.set_default_branch(
        portfolio_id, 
        application_id, 
        project_id, 
        branch['id'], 
        polaris_branch_name
    )
    
    if success:
        print(f"Successfully set '{polaris_branch_name}' as the default branch for '{polaris_project_name}'")
        sys.exit(0)
    else:
        print("Failed to set default branch")
        sys.exit(1)


if __name__ == "__main__":
    main()
