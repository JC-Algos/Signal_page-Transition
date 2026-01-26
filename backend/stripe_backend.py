import os
import stripe
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
from supabase import create_client, Client

# ==========================================
# LOAD ENVIRONMENT VARIABLES FROM .env FILE
# ==========================================
from dotenv import load_dotenv

# Load .env from same directory as this script
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

# Also try loading from current working directory
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 1. CONFIGURATION (FROM ENVIRONMENT VARIABLES)
# ==========================================

# Stripe Keys
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '').strip()
ENDPOINT_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '').strip()

# Supabase Keys
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip()
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '').strip()

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# Website URL
WEBSITE_BASE_URL = os.environ.get('WEBSITE_BASE_URL', 'https://www.jc-algos.com')

# Price IDs
PRICE_IDS = {
    'basic_monthly': os.environ.get('STRIPE_PRICE_MONTHLY', 'price_1SnjiK1JIZhXOZpFl8dhRnTu'),
    'basic_annual': os.environ.get('STRIPE_PRICE_ANNUAL', 'price_1Strgb1JIZhXOZpFoZZWjhrr')
}

# Intro offer coupon
INTRO_COUPON_ID = os.environ.get('STRIPE_INTRO_COUPON', 'brc9vWay')

# Free trial days
FREE_TRIAL_DAYS = int(os.environ.get('FREE_TRIAL_DAYS', '7'))


@app.route('/api/stripe/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy', 
        'version': '4.1 (Fixed promo/discount conflict)',
        'stripe_configured': bool(stripe.api_key),
        'supabase_configured': bool(supabase)
    })


# ==========================================
# 2. CHECKOUT (PAYMENT)
# ==========================================
@app.route('/api/stripe/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        data = request.json or {}
        user_email = data.get('email')
        user_id = data.get('user_id')
        price_id = data.get('price_id', PRICE_IDS['basic_monthly'])

        logger.info(f"Attempting Checkout for: {user_email}, price: {price_id}")

        if not user_email or not user_id:
            return jsonify({'error': 'Missing email or user_id'}), 400

        # Check if user is new (no previous subscription)
        is_new_user = True
        try:
            customers = stripe.Customer.list(email=user_email, limit=1)
            if customers.data:
                subs = stripe.Subscription.list(customer=customers.data[0].id, limit=1)
                if subs.data:
                    is_new_user = False
                    logger.info(f"Returning customer detected: {user_email}")
        except Exception as e:
            logger.warning(f"Error checking customer history: {e}")

        # Build subscription data
        subscription_data = {
            'metadata': {'user_id': user_id}
        }

        # Apply intro offer for new monthly subscribers only
        discounts = []
        is_monthly = price_id == PRICE_IDS['basic_monthly']
        
        if is_new_user and is_monthly:
            subscription_data['trial_period_days'] = FREE_TRIAL_DAYS
            logger.info(f"Applying {FREE_TRIAL_DAYS}-day trial for new user: {user_email}")
            
            if INTRO_COUPON_ID:
                discounts = [{'coupon': INTRO_COUPON_ID}]
                logger.info(f"Applying intro coupon {INTRO_COUPON_ID} for new user: {user_email}")

        # Build checkout params
        checkout_params = {
            'payment_method_types': ['card'],
            'line_items': [{'price': price_id, 'quantity': 1}],
            'mode': 'subscription',
            'success_url': f'{WEBSITE_BASE_URL}/index.html?subscription=success',
            'cancel_url': f'{WEBSITE_BASE_URL}/subscribe.html?cancelled=true',
            'customer_email': user_email,
            'subscription_data': subscription_data
        }

        # FIX: Only add ONE of these - discounts OR allow_promotion_codes, not both
        if discounts:
            checkout_params['discounts'] = discounts
            # Don't add allow_promotion_codes when auto-applying coupon
        else:
            # Only allow manual promo codes if no auto-discount
            checkout_params['allow_promotion_codes'] = True

        checkout_session = stripe.checkout.Session.create(**checkout_params)

        logger.info(f"Checkout session created: {checkout_session.id}")

        return jsonify({
            'id': checkout_session.id,
            'url': checkout_session.url,
            'is_new_user': is_new_user,
            'has_trial': is_new_user and is_monthly
        })

    except Exception as e:
        logger.error(f"CRITICAL STRIPE ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ==========================================
# 3. CUSTOMER PORTAL (MANAGE/CANCEL)
# ==========================================
@app.route('/api/stripe/create-portal-session', methods=['POST'])
def create_portal_session():
    try:
        data = request.json or {}
        user_email = data.get('email')

        if not user_email:
            return jsonify({'error': 'Email is required'}), 400

        customers = stripe.Customer.list(email=user_email, limit=1)
        if not customers.data:
            return jsonify({'error': 'No Stripe customer found'}), 404

        portal_session = stripe.billing_portal.Session.create(
            customer=customers.data[0].id,
            return_url=f'{WEBSITE_BASE_URL}/index.html'
        )

        return jsonify({'url': portal_session.url})

    except Exception as e:
        logger.error(f"Error creating portal: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ==========================================
# 4. WEBHOOK (THE AUTOMATION)
# ==========================================
@app.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, ENDPOINT_SECRET)
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    event_type = event['type']
    data = event['data']['object']

    logger.info(f"Received event: {event_type}")

    if event_type == 'checkout.session.completed':
        user_id = data.get('metadata', {}).get('user_id')
        
        subscription_id = data.get('subscription')
        if not user_id and subscription_id:
             try:
                 sub = stripe.Subscription.retrieve(subscription_id)
                 user_id = sub.get('metadata', {}).get('user_id')
             except Exception:
                 pass

        if user_id and supabase:
            logger.info(f"✅ Payment Success! Upgrading: {user_id}")
            supabase.table('user_profiles').update({
                'subscription_status': 'active',
                'membership_status': 'premium',
                'stripe_customer_id': data.get('customer')
            }).eq('id', user_id).execute()

    elif event_type == 'customer.subscription.deleted':
        user_id = data.get('metadata', {}).get('user_id')
        
        if user_id and supabase:
            logger.info(f"🚫 Subscription Cancelled. Downgrading: {user_id}")
            supabase.table('user_profiles').update({
                'subscription_status': 'cancelled',
                'membership_status': 'free'
            }).eq('id', user_id).execute()

    elif event_type == 'customer.subscription.updated':
        user_id = data.get('metadata', {}).get('user_id')
        status = data.get('status')
        
        if user_id and supabase:
            logger.info(f"📝 Subscription updated for user {user_id}, status: {status}")
            
            if status in ['active', 'trialing']:
                supabase.table('user_profiles').update({
                    'subscription_status': status,
                    'membership_status': 'premium'
                }).eq('id', user_id).execute()

    elif event_type == 'customer.subscription.created':
        user_id = data.get('metadata', {}).get('user_id')
        status = data.get('status')
        
        if user_id and supabase:
            logger.info(f"🆕 New subscription created for user {user_id}, status: {status}")
            
            if status in ['active', 'trialing']:
                supabase.table('user_profiles').update({
                    'subscription_status': status,
                    'membership_status': 'premium',
                    'stripe_customer_id': data.get('customer')
                }).eq('id', user_id).execute()

    return jsonify({'received': True})


if __name__ == '__main__':
    if not stripe.api_key:
        logger.warning("⚠️ STRIPE_SECRET_KEY not set!")
    if not ENDPOINT_SECRET:
        logger.warning("⚠️ STRIPE_WEBHOOK_SECRET not set!")
    if not supabase:
        logger.warning("⚠️ Supabase not configured!")
    
    logger.info(f"🔧 Config loaded - Stripe: {'✅' if stripe.api_key else '❌'}, Supabase: {'✅' if supabase else '❌'}")
    
    app.run(host='0.0.0.0', port=5007)
