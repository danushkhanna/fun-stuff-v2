"""
WebGuard: A Comprehensive Fuzzer for Web Application Security
Automatically generated by Colaboratory.
Original file is located at
    https://colab.research.google.com/drive/13PhvS9RucBMO-DViNrLIu1aaYttGWiT0
"""

import streamlit as st
import pickle
import pandas as pd
from extract_features import ExtractFeatures
from PIL import Image
import requests
import dns.resolver
from urllib.parse import urljoin
from pymisp import PyMISP
import re
import validators
import json
import urllib.parse

# Load images
image2 = Image.open('webguard.jpg')
image = Image.open('sihlogo.jpg')

# Streamlit UI for logos
col1, col2, col3 = st.columns([0.001, 8, 3])
with col2:
    st.image(image2, width=175)
with col3:
    st.image(image, width=150)

st.markdown(
    "<div style='display: flex; align-items: center; margin-bottom: -35px;'>"
    "<h1 style='color:#0062ff; margin-center: 10px;'>WebGuard:</h1>"
    "</div>"
    "<h1 style='color:black; margin-center: 10px;'>A Comprehensive Fuzzer for Web Application Security</h1>",
    unsafe_allow_html=True
)


# Caching the phishing URL detection model
@st.cache_resource


def initialize_dnsdumpster():
    try:
        api_key = st.secrets["DNSDUMPSTER_API_KEY"]
        return api_key
    except Exception as e:
        st.error(f"Failed to initialize DNSDumpster: {str(e)}")
        return None


def query_dnsdumpster(domain):
    api_key = initialize_dnsdumpster()
    if not api_key:
        return None
    
    headers = {
        'X-API-Key': api_key
    }
    
    try:
        response = requests.get(
            f'https://api.dnsdumpster.com/domain/{domain}',
            headers=headers
        )
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"DNSDumpster API error: {str(e)}")
        return None
    

def analyze_dns_data(dns_data):
    findings = {
        'subdomains': set(),
        'ip_addresses': set(),
        'potential_apis': set()
    }
    
    if not dns_data:
        return findings
    
    # Extract A records
    for record in dns_data.get('a', []):
        findings['subdomains'].add(record['host'])
        for ip_info in record['ips']:
            findings['ip_addresses'].add(ip_info['ip'])
            # Check for API endpoints in banners
            if 'banners' in ip_info:
                for protocol in ['http', 'https']:
                    if protocol in ip_info['banners']:
                        banner = ip_info['banners'][protocol]
                        if 'api' in banner.get('title', '').lower():
                            findings['potential_apis'].add(f"{protocol}://{ip_info['ip']}")

    # Extract CNAME records
    for record in dns_data.get('cname', []):
        findings['subdomains'].add(record['host'])
        
    return findings


def initialize_misp():
    try:
        misp_url = st.secrets["MISP_URL"]  # Configure in Streamlit secrets
        misp_key = st.secrets["MISP_API_KEY"]
        verify_ssl = False  # Set to True in production
        return PyMISP(misp_url, misp_key, verify_ssl)
    except Exception as e:
        st.error(f"Failed to initialize MISP: {str(e)}")
        return None
    

def identify_input_type(text):
    if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text):
        return 'ip-dst'
    elif validators.domain(text):
        return 'domain'
    elif validators.email(text):
        return 'email'
    else:
        return 'url'




def get_model():
    with open('phishing_url_detector.pkl', 'rb') as pickle_model:
        phishing_url_detector = pickle.load(pickle_model)
    return phishing_url_detector

# Directory enumeration and file brute-forcing
COMMON_DIRECTORIES = ["admin", "login", "test", "backup"]
COMMON_EXTENSIONS = [".php", ".html", ".asp", ".js"]
COMMON_SUBDOMAINS = ["www", "api", "mail", "ftp"]

# Function to check if a URL returns a 404 error
def check_404(url):
    try:
        response = requests.head(url, timeout=10)  # Use HEAD request for faster checking
        return response.status_code == 404
    except requests.RequestException:
        return False

# Function to brute force valid URLs (directories and files)
def brute_force_url(base_url):
    found_urls = []
    for directory in COMMON_DIRECTORIES:
        for ext in COMMON_EXTENSIONS:
            full_url = urljoin(base_url, f"{directory}{ext}")
            if not check_404(full_url):
                found_urls.append(full_url)
    return found_urls

# Function to brute force Virtual Hosts (subdomains)
def fuzz_virtual_hosts(domain):
    found_vhosts = []
    for subdomain in COMMON_SUBDOMAINS:
        vhost = f"{subdomain}.{domain}"
        try:
            response = requests.get(f"http://{vhost}", timeout=10)
            if response.status_code == 200:
                found_vhosts.append(vhost)
        except requests.RequestException:
            continue
    return found_vhosts

# API endpoint fuzzing
API_ENDPOINTS = ["/api/v1/", "/api/v2/", "/api/user/", "/api/admin/"]
def test_api_endpoints(base_url):
    found_endpoints = []
    for endpoint in API_ENDPOINTS:
        full_url = urljoin(base_url, endpoint)
        try:
            response = requests.get(full_url, timeout=10)
            if response.status_code == 200:
                found_endpoints.append(full_url)
        except requests.RequestException:
            continue
    return found_endpoints

# URL parameter fuzzing
def fuzz_parameters(base_url):
    payloads = ["' OR 1=1 --", "<script>alert('XSS')</script>", "../etc/passwd"]
    found_vulnerabilities = []
    for payload in payloads:
        fuzzed_url = f"{base_url}?param={payload}"
        try:
            response = requests.get(fuzzed_url, timeout=10)
            if response.status_code == 200:
                found_vulnerabilities.append(fuzzed_url)
        except requests.RequestException:
            continue
    return found_vulnerabilities

# Subdomain brute force discovery
def discover_subdomains(domain):
    found_subdomains = []
    for subdomain in COMMON_SUBDOMAINS:
        try:
            resolved = dns.resolver.resolve(f"{subdomain}.{domain}", 'A')
            found_subdomains.append(f"{subdomain}.{domain}")
        except (dns.resolver.NXDOMAIN, dns.resolver.Timeout):
            continue
    return found_subdomains

# Original code starts here


# Takes in user input
input_url = st.text_area("Enter URL, IP, Domain, or Email for security analysis:")
if input_url != "":
    # Extract features from the URL
    features_url = ExtractFeatures().url_to_features(url=input_url)
    
    # Extract domain for DNS analysis
    try:
        parsed_url = urllib.parse.urlparse(input_url)
        domain = parsed_url.netloc if parsed_url.netloc else input_url.split('/')[0]
    
        # DNSDumpster Analysis
        st.write("🔍 Performing DNS enumeration...")
        dns_data = query_dnsdumpster(domain)
        if dns_data:
            findings = analyze_dns_data(dns_data)
            
            if findings['subdomains']:
                st.write("📡 Discovered Subdomains:")
                for subdomain in findings['subdomains']:
                    st.write(f"- {subdomain}")
                    
            if findings['ip_addresses']:
                st.write("🌐 Associated IP Addresses:")
                for ip in findings['ip_addresses']:
                    st.write(f"- {ip}")
                    
            if findings['potential_apis']:
                st.write("🔌 Potential API Endpoints:")
                for api in findings['potential_apis']:
                    st.write(f"- {api}")
                    # Additional API endpoint fuzzing
                    api_results = test_api_endpoints(api)
                    if api_results:
                        st.write("  Found active endpoints:")
                        for endpoint in api_results:
                            st.write(f"  - {endpoint}")

        # Initialize MISP
        misp = initialize_misp()
        
        # MISP Threat Intelligence Check
        if misp:
            st.write("Checking MISP threat intelligence database...")
            try:
                input_type = identify_input_type(input_url)
                results = misp.search(controller='attributes', value=input_url, type=input_type)
                
                if results:
                    st.warning("🚨 MISP Alert: This indicator is associated with known threats!")
                    for result in results:
                        if 'Event' in result:
                            st.write(f"- Event ID: {result['Event']['id']}")
                            st.write(f"- Threat Level: {result['Event']['threat_level_id']}")
                            st.write(f"- Description: {result['Event'].get('info', 'No description available')}")
                            st.write("---")
                else:
                    st.success("✅ No matches found in MISP database")
            except Exception as e:
                st.error(f"MISP lookup failed: {str(e)}")

        # URL Status Check and Brute Force
        final_url = input_url
        if input_url.endswith("404/"):
            final_url = input_url.rsplit("404/", 1)[0]
            st.write(f"{input_url} - Removed '404/': {final_url}")

        response = requests.get(final_url)
        if response.status_code == 200:
            st.write(f"{final_url} Status: 200 (OK) - The website is live and running")
        else:
            st.write(f"{final_url} Status: {response.status_code} - The website may have issues")

        if check_404(final_url):
            st.write(f"{final_url} Status: 404 (Not Found) - Initiating Brute Force")
            possible_urls = brute_force_url(final_url)
            if possible_urls:
                final_url = possible_urls[0]
                st.write(f"Brute-forced URL: {final_url}")
            else:
                st.write("No valid URLs found based on the wordlist")

    except requests.RequestException as e:
        st.write(f"Connection error: {str(e)}")
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

    # Function to brute force valid URLs
    def brute_force_url(base_url):
        # This is a simple wordlist for the sake of demonstration.
        # In real scenarios, you might read from a .txt file.
        wordlist = ['about', 'contact', 'login', 'signup', 'user', 'admin']
        found_urls = []
        for word in wordlist:
            # Construct new URL to check
            new_url = base_url + "/" + word
            if not check_404(new_url):
                found_urls.append(new_url)
        return found_urls

    if input_url != "":
        # Initialize a variable to store the final URL
        final_url = input_url
        # Check if the input URL ends with "404/" and remove it
        if input_url.endswith("404/"):
            final_url = input_url.rsplit("404/", 1)[0]
            st.write(f"{input_url} - Removed '404/': {final_url}")
        try:
            response = requests.get(final_url)  # Send a GET request to the URL
            if response.status_code == 200:
                st.write(f"{final_url} Status: 200 (OK) - The website is live and running")
            else:
                st.write(f"{final_url} Status: {response.status_code} - The website may have issues")

            if check_404(final_url):
                st.write(f"{final_url} Status: 404 (Not Found) - Initiating Brute Force")

                # Try to brute force the correct URL by modifying the final_url
                possible_urls = brute_force_url(final_url)
                if possible_urls:
                    final_url = possible_urls[0]  # Use the first valid URL found
                    st.write(f"Brute-forced URL: {final_url}")
                else:
                    st.write("No valid URLs found based on the wordlist")
        except requests.RequestException as e:
            st.write(f"{final_url} NA FAILED TO CONNECT {str(e)}")
        except Exception as e:
            print(e)
            st.error("Not sure what went wrong. We'll get back to you shortly.")

        # Extract and predict using model
        features_url = ExtractFeatures().url_to_features(url=final_url)
        features_dataframe = pd.DataFrame.from_dict([features_url])
        features_dataframe = features_dataframe.fillna(-1)
        features_dataframe = features_dataframe.astype(int)
        st.cache_data.clear()
        prediction_str = ""
        try:
            phishing_url_detector = get_model()
            prediction = phishing_url_detector.predict(features_dataframe)
            if prediction == int(True):
                prediction_str = 'This website might be malicious!'
            elif prediction == int(False):
                prediction_str = 'Website is safe to proceed!'
            else:
                prediction_str = ''
            st.write(prediction_str)
            st.write(features_dataframe)
        except Exception as e:
            print(e)
            st.error("Not sure what went wrong. We'll get back to you shortly!")
else:
    st.write("")

# Username and password brute-force
usernames = ['user1', 'user2', 'admin']
passwords = ['password1', 'password2', '123456']
login_url = 'https://example.com/login'  # Replace with the actual URL

# Session object to maintain the session cookies
session = requests.Session()

# Loop through the username and password pairs
for username in usernames:
    for password in passwords:
        # Prepare the login data
        login_data = {
            'username': username,
            'password': password
        }

        response = session.post(login_url, data=login_data)
        if 'Login Successful' in response.text:
            print(f"Successful login - Username: {username}, Password: {password}")
            break

# Close the session
session.close()

# Summary of the solution
# Summary of the solution
st.markdown("Our chosen problem statement focused on Web Safety through URL fuzzing, status check, and brute-forcing exceptions and authentications. Please try the interactive input above and let us know your feedback.")
st.markdown("### *Key Objectives*")
st.markdown("- **URL-Based Feature Extraction and Fuzzing**: Machine Learning-Based Approaches for determining the authenticity of an input URL.")
st.markdown("- **Live URL Detection**: Uses HTTPS GET command to call the input URL as an argument, obtaining the site status and displaying the result in the frontend.")
st.markdown("- **404 Error Handling**: Brute-forcing URL modifications to resolve 404 errors using predefined vocabulary for appending/prepending.")
st.markdown("- **Login Authentication Testing**: Attempts login authentication using brute-force methods, iterating through different username and password combinations.")

# Display Results Section
st.markdown("### *Results*")
st.markdown("Our solution provides a robust and reliable method for delivering the mentioned features. Although it was developed under time constraints for the Smart India Hackathon 2024, we believe that with more time and resources, this prototype can evolve into an industry-scalable solution. Feel free to contact any of our team members if you'd like to contribute!")

# Closing Remarks
st.markdown("### *Future Enhancements*")
st.markdown("- Add more sophisticated payloads for fuzzing URL parameters to cover a wider range of vulnerabilities.")
st.markdown("- Enhance the login brute-force function with support for CAPTCHAs and multi-factor authentication bypass.")
st.markdown("- Integrate results into a comprehensive reporting format that details vulnerability findings with severity ratings.")
st.markdown("- Implement multi-threading to speed up brute-forcing tasks.")
