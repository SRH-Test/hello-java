#!/usr/bin/env python3


import os
import requests
import json

def test_exact_curl():
    server_url = os.getenv('POLARIS_SERVER_URL', 'https://poc.polaris.blackduck.com')
    access_token = os.getenv('POLARIS_ACCESS_TOKEN')
    
    if not access_token:
        print("POLARIS_ACCESS_TOKEN not found")
        return False
    
    print(f"Testing exact curl equivalent")
    print(f"Server: {server_url}")
    print(f"Token length: {len(access_token)}")
    
    # Exact headers from your working curl
    headers = {
        'Api-Token': access_token,
        'Accept': 'application/json'
    }
    
    print(f"Request headers: {headers}")
    
    try:
        # Test portfolios endpoint
        url = f"{server_url}/api/portfolios"
        print(f"Making GET request to: {url}")
        
        response = requests.get(url, headers=headers, timeout=30)
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("SUCCESS!")
            data = response.json()
            print(f"Portfolios found: {len(data.get('_items', []))}")
            
            if data.get('_items'):
                portfolio = data['_items'][0]
                portfolio_id = portfolio['id']
                print(f"First portfolio ID: {portfolio_id}")
                
                # Test getting applications
                apps_url = f"{server_url}/api/portfolios/{portfolio_id}/applications"
                print(f"Testing applications endpoint: {apps_url}")
                
                apps_response = requests.get(apps_url, headers=headers, timeout=30)
                print(f"Applications response status: {apps_response.status_code}")
                
                if apps_response.status_code == 200:
                    apps_data = apps_response.json()
                    print(f"Applications found: {len(apps_data.get('_items', []))}")
                    
                    # Look for your specific application
                    for app in apps_data.get('_items', []):
                        if app['name'] == 'SRH-hello-java':
                            print(f"Found target application: {app['name']} (ID: {app['id']})")
                            return True
                
            return True
        else:
            print(f"FAILED. Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    test_exact_curl()
