import requests
import time
import re
import json
from typing import Dict, Optional, List

# Zeus-X API settings
ZEUS_API_URL = "https://api.zeus-x.ru"
PURCHASE_API_URL = f"{ZEUS_API_URL}/purchase"
INSTOCK_API_URL = f"{ZEUS_API_URL}/instock"
BALANCE_API_URL = f"{ZEUS_API_URL}/balance"

API_KEY = "76617271f0b44f86a67fe89f9522337d"

# Disable warnings
requests.packages.urllib3.disable_warnings()


class DiscordLinkExtractor:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or API_KEY
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        })


    def check_balance(self) -> Optional[float]:
        """Check remaining account balance"""
        try:
            url = f"{BALANCE_API_URL}?apikey={self.api_key}"
            print("Checking balance...")
            
            response = self.session.get(url, verify=False, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, dict):
                    if 'Balance' in data:
                        balance = data['Balance']
                        print(f"Remaining balance: ${balance}")
                        return float(balance)
                print(f"Invalid data format: {data}")
            else:
                print(f"HTTP Error: {response.status_code}")
            return None
            
        except Exception as e:
            print(f"Error checking balance: {e}")
            return None


    def check_instock(self) -> Optional[List[Dict]]:
        """Check available accounts in stock"""
        try:
            print("Checking available accounts...")
            response = self.session.get(INSTOCK_API_URL, verify=False, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, dict) and 'Data' in data:
                    accounts_data = data['Data']
                    if isinstance(accounts_data, list) and len(accounts_data) > 0:
                        print("Available accounts:")
                        for item in accounts_data:
                            if isinstance(item, dict):
                                account_code = item.get('AccountCode', 'Unknown')
                                name = item.get('Name', 'Unknown')
                                price = item.get('Price', 0)
                                instock = item.get('Instock', 0)
                                print(f"   {account_code} - {name}: ${price} ({instock} available)")
                        return accounts_data
                
                print("Invalid data format")
            else:
                print(f"HTTP Error: {response.status_code}")
            return None
            
        except Exception as e:
            print(f"Error checking instock: {e}")
            return None


    def purchase_email(self, account_type: str = "HOTMAIL_TRUSTED_GRAPH_API") -> Optional[Dict]:
        """Purchase new email and return its data"""
        
        account_type = account_type.upper()
        
        try:
            url = f"{PURCHASE_API_URL}?apikey={self.api_key}&accountcode={account_type}&quantity=1"
            
            print(f"Purchasing email type: {account_type}...")
            response = self.session.get(url, verify=False, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, dict) and data.get('Code') == 0:
                    if 'Data' in data and isinstance(data['Data'], dict):
                        purchase_data = data['Data']
                        
                        if 'Accounts' in purchase_data and isinstance(purchase_data['Accounts'], list):
                            accounts = purchase_data['Accounts']
                            
                            if len(accounts) > 0:
                                account = accounts[0]
                                
                                email_ = account.get('Email', '')
                                password = account.get('Password', '')
                                refresh_token = account.get('RefreshToken', '')
                                client_id = account.get('ClientId', '')
                                
                                if email_:
                                    print(f"Successfully purchased email: {email_}")
                                    
                                    return {
                                        "email": email_,
                                        "password": password,
                                        "refresh_token": refresh_token,
                                        "client_id": client_id,
                                        "type": account_type,
                                        "purchase_id": purchase_data.get('PurchaseId', ''),
                                        "price": purchase_data.get('UnitPrice', 0),
                                        "raw_data": data
                                    }
            
            print(f"Failed to purchase email")
            return None

        except Exception as e:
            print(f"Error purchasing email: {e}")
            return None

    def check_email_messages(self, email_data: Dict, max_attempts: int = 60) -> Optional[Dict]:
        """Check messages in email"""
        try:
            print("Checking messages...")
            
            mail_api_url = "https://gapi.hotmail007.com/v1/mail/getFirstMail"
            client_key = "165dfb5153f245798856f7cf03c15c00977479"
            
            account_string = f"{email_data['email']}:{email_data['password']}"
            
            if email_data.get('refresh_token') and email_data.get('client_id'):
                account_string = f"{email_data['email']}:{email_data['password']}:{email_data['refresh_token']}:{email_data['client_id']}"
            
            attempts = 0
            while attempts < max_attempts:
                attempts += 1
                
                try:
                    url = f"{mail_api_url}?clientKey={client_key}&account={account_string}&folder=inbox"
                    
                    response = self.session.get(url, verify=False, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if data.get("code") == 0 and data.get("success"):
                            email_info = data.get("data", {})
                            
                            if email_info and (email_info.get('subject') or email_info.get('Text') or email_info.get('Html')):
                                subject = email_info.get('subject', 'No Subject')
                                from_email = email_info.get('from', 'Unknown Sender')
                                
                                print(f"Message ({attempts}/{max_attempts}): {subject[:50]}...")
                                
                                body_content = self.extract_email_content(email_info)
                                
                                # Search for Discord link in message
                                discord_link = self.find_discord_verification_link(body_content, subject)
                                
                                if discord_link:
                                    print(f"Found Discord verification link!")
                                    return {
                                        "success": True,
                                        "found": True,
                                        "discord_link": discord_link,
                                        "subject": subject,
                                        "from": from_email,
                                        "attempts": attempts,
                                        "content": body_content[:500]
                                    }
                                elif 'discord' in subject.lower():
                                    print("This is a Discord message but link is not clear...")
                                    # Save message for debugging
                                    self.debug_discord_email(body_content)
                            
                except Exception as e:
                    pass
                
                if attempts < max_attempts:
                    time.sleep(3)
            
            return {"success": True, "found": False, "attempts": attempts}
            
        except Exception as e:
            print(f"Error checking messages: {e}")
            return {"success": False, "error": str(e)}

    def extract_email_content(self, email_info: Dict) -> str:
        """Extract message content"""
        html_content = email_info.get('Html', '')
        if html_content and html_content != 'No Content':
            return html_content
        
        text_content = email_info.get('Text', '')
        if text_content and text_content != 'No Content':
            return text_content
        
        return ''

    def debug_discord_email(self, html_content: str):
        """Save email content for debugging"""
        try:
            # Look at first 2000 chars only
            preview = html_content[:2000]
            
            # Search for any discord mention
            if 'discord' in preview.lower():
                print("Found discord mention in message")
                
                # Try to find patterns
                patterns = [
                    r'https://[^\s"\']*discord[^\s"\']*',
                    r'verify[^\s"\']*token[^\s"\']*',
                    r'token=[^\s"\']*',
                    r'code=[^\s"\']*',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, preview, re.IGNORECASE)
                    for match in matches:
                        print(f"   Pattern match: {match[:100]}...")
        
        except Exception as e:
            pass

  
    def find_discord_verification_link(self, message_body: str, subject: str = "") -> Optional[str]:
        """Search for Discord verification link"""
        try:
            if not message_body:
                return None
            
            print("Searching for verification link...")
            
            # First: Search for direct link in HTML
            direct_link = self.find_direct_verify_link(message_body)
            if direct_link:
                return direct_link
            
            # Second: Search for click.discord links and try to resolve them
            click_links = self.find_click_discord_links(message_body)
            
            for click_link in click_links:
                print(f"Found click.discord link: {click_link[:80]}...")
                resolved_link = self.resolve_click_discord_link(click_link)
                
                if resolved_link and self.is_valid_discord_verify_link(resolved_link):
                    return resolved_link
            
            # Third: Search for any link with token or code
            token_link = self.find_token_link(message_body)
            if token_link:
                return token_link
            
            print("No clear verification link found")
            return None
            
        except Exception as e:
            print(f"Search error: {e}")
            return None

    def find_direct_verify_link(self, html_content: str) -> Optional[str]:
        """Search for direct verification link"""
        patterns = [
            # https://discord.com/verify#token=...
            r'https://discord\.com/verify[^\s"\'\<\>]*',
            
            # https://discord.com/api/v9/auth/verify/...
            r'https://discord\.com/api/v[0-9]+/auth/verify[^\s"\'\<\>]*',
            
            # https://discord.com/verify-email?token=...
            r'https://discord\.com/verify-email[^\s"\'\<\>]*',
            
            # https://discord.com/activate?token=...
            r'https://discord\.com/activate[^\s"\'\<\>]*',
            
            # Any discord.com link with token or code
            r'https://discord\.com/[^\s"\'\<\>]*[?&](token|code)=[^\s"\'\<\>]*',
            
            # discordapp.com
            r'https://discordapp\.com/[^\s"\'\<\>]*verify[^\s"\'\<\>]*',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for link in matches:
                if link and ('verify' in link.lower() or 'activate' in link.lower() or 'token=' in link.lower()):
                    print(f"Found direct verification link: {link[:100]}...")
                    return link
        
        return None

    def find_click_discord_links(self, html_content: str) -> List[str]:
        """Find all click.discord.com links"""
        pattern = r'https://click\.discord\.com/[^\s"\'\<\>]*'
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        return matches

    def find_token_link(self, html_content: str) -> Optional[str]:
        """Search for any link with token"""
        # Search for href with token
        href_patterns = [
            r'href=["\']([^"\']*token[^"\']*)["\']',
            r'href=["\']([^"\']*code[^"\']*)["\']',
            r'href=["\']([^"\']*verify[^"\']*)["\']',
        ]
        
        for pattern in href_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for link in matches:
                if link and ('discord.com' in link or 'discordapp.com' in link):
                    print(f"Found token link: {link[:100]}...")
                    if 'click.discord.com' in link:
                        resolved = self.resolve_click_discord_link(link)
                        if resolved and self.is_valid_discord_verify_link(resolved):
                            return resolved
                    elif self.is_valid_discord_verify_link(link):
                        return link
        
        return None

    def resolve_click_discord_link(self, click_url: str) -> Optional[str]:
        """Resolve click.discord.com links intelligently"""
        try:
            print(f"Resolving: {click_url[:60]}...")
            

            response = requests.get(
                click_url, 
                allow_redirects=False, 
                timeout=15, 
                verify=False,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                }
            )
            

            if response.status_code in [301, 302, 303, 307, 308]:
                redirect_url = response.headers.get('Location', '')
                if redirect_url:
                    print(f"   Redirect to: {redirect_url[:80]}...")
                    
                    # If this is also click.discord, resolve it again
                    if 'click.discord.com' in redirect_url:
                        return self.resolve_click_discord_link(redirect_url)
                    else:
                        return redirect_url
            

            print(f"   No redirect, returning same URL")
            return click_url
            
        except Exception as e:
            print(f"Error resolving: {e}")
            return None

    def is_valid_discord_verify_link(self, url: str) -> bool:
        """Verify if this is a real Discord verification link"""
        if not url:
            return False
        
        if 'discord.com' not in url and 'discordapp.com' not in url:
            return False
        

        if ('verify' in url.lower() or 
            'activate' in url.lower() or 
            'token=' in url.lower() or 
            'code=' in url.lower()):
            return True
        
        return False


    def find_discord_verification(self, email_data: Dict) -> Optional[str]:
        """Search for Discord link in email"""
        print(f"\nSearching for Discord link in: {email_data['email']}")
        print("=" * 60)
        
        # Check messages
        result = self.check_email_messages(email_data, max_attempts=60)
        
        if result.get('success') and result.get('found'):
            discord_link = result.get('discord_link')
            if discord_link and self.is_valid_discord_verify_link(discord_link):
                print(f"Found link on attempt {result.get('attempts', 'N/A')}")
                return discord_link
            else:
                print("Link found is not a valid verification link")
        
        print("No Discord verification link found in email")
        return None

    def quick_find_discord_link(self):
        """Main function for quick search"""
        
        # First: Check balance
        balance = self.check_balance()
        if balance is None:
            print("Cannot check balance")
            return None
            
        if balance <= 0.002:
            print(f"Insufficient balance! Balance: ${balance}")
            return None
        

        print("\nChecking available accounts...")
        accounts = self.check_instock()
        
        if not accounts:
            print("No accounts available")
            return None
        

        account_type = "HOTMAIL_TRUSTED_GRAPH_API"
        for acc in accounts:
            if isinstance(acc, dict) and acc.get('AccountCode') == 'HOTMAIL_TRUSTED_GRAPH_API' and acc.get('Instock', 0) > 0:
                account_type = 'HOTMAIL_TRUSTED_GRAPH_API'
                break
        

        print(f"\nPurchasing email type: {account_type}...")
        email_data = self.purchase_email(account_type)
        
        if not email_data:
            print("Failed to purchase email")
            return None

        print(f"\nSuccessfully purchased email:")
        print(f"   Email: {email_data['email']}")
        print(f"   Password: {email_data['password']}")
        print(f"   Type: {email_data.get('type', 'Unknown')}")
        print(f"   Price: ${email_data.get('price', 0)}")
        

        print("\nSearching for Discord message...")
        discord_link = self.find_discord_verification(email_data)

        if discord_link:
            print("\n" + "=" * 30)
            print("FOUND VERIFICATION LINK!")
            print("=" * 30)
            

            print(f"\nReal verification link:")
            print(f"{discord_link}")
            

            if self.is_valid_discord_verify_link(discord_link):
                print("Link is valid for verification!")
            else:
                print("Link might not be valid for verification")
            
            print("\n" + "=" * 30)

            try:
                with open("discord_links.txt", "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Email: {email_data['email']}\n")
                    f.write(f"Password: {email_data['password']}\n")
                    f.write(f"Link:\n{discord_link}\n")
                    
                    # If token in link, save it too
                    if 'token=' in discord_link:
                        token_part = discord_link.split('token=')[1]
                        if len(token_part) > 10:
                            f.write(f"Token: {token_part[:50]}...\n")
                    
                    f.write(f"{'='*60}\n\n")
                print("Link saved to discord_links.txt")
            except Exception as e:
                print(f"Cannot save: {e}")

            return discord_link

        print("\nNo Discord verification link found")
        return None



def main():
    print("Discord Link Finder - Zeus-X Edition")
    print("=" * 50)

    print("=" * 50)

    api_key = input(f"Enter API Key (Enter for default): ").strip()
    if not api_key:
        api_key = API_KEY
        print("Using default API Key")

    extractor = DiscordLinkExtractor(api_key)

    while True:
        print("\n" + "=" * 50)
        print("1- Start Discord link search")
        print("2- Check balance")
        print("3- Check available accounts")
        print("4- Manually select email type")
        print("5- Exit")
        print("=" * 50)

        choice = input("Your choice: ").strip()

        if choice == "1":
            print("\n" + "=" * 20)
            print("Starting automatic search...")
            print("=" * 20)
            
            start_time = time.time()
            result = extractor.quick_find_discord_link()
            end_time = time.time()
            
            duration = end_time - start_time
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            
            print(f"\nSearch time: {minutes} minutes and {seconds} seconds")
            
        elif choice == "2":
            extractor.check_balance()
            
        elif choice == "3":
            extractor.check_instock()
            
        elif choice == "4":
            print("\nSelect email type (best for Discord):")
            print("1- HOTMAIL_TRUSTED_GRAPH_API (best - $0.01)")
            print("2- HOTMAIL_TRUSTED ($0.01)")
            print("3- HOTMAIL ($0.002)")
            print("4- OUTLOOK ($0.002)")
            
            acc_choice = input("Choice (1-4): ").strip()
            
            account_map = {
                '1': 'HOTMAIL_TRUSTED_GRAPH_API',
                '2': 'HOTMAIL_TRUSTED',
                '3': 'HOTMAIL',
                '4': 'OUTLOOK'
            }
            
            account_type = account_map.get(acc_choice, 'HOTMAIL_TRUSTED_GRAPH_API')
            print(f"Purchasing email type: {account_type}")
            
            start_time = time.time()
            email_data = extractor.purchase_email(account_type)
            
            if email_data:
                print(f"\nSuccessfully purchased email!")
                print(f"Email: {email_data['email']}")
                

                discord_link = extractor.find_discord_verification(email_data)
                
                if discord_link:
                    print(f"\nLink: {discord_link}")
                    

                    if extractor.is_valid_discord_verify_link(discord_link):
                        print("Link is valid for verification!")
                    else:
                        print("Link might not be valid")
                else:
                    print("\nNo Discord link found")
            
            end_time = time.time()
            duration = end_time - start_time
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            print(f"\nSearch time: {minutes} minutes and {seconds} seconds")
            
        elif choice == "5":
            print("Goodbye!")
            break
            
        else:
            print("Invalid choice, try again")


if __name__ == "__main__":
    main()