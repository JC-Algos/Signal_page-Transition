import os
import stripe
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
from supabase import create_client, Client

# Load environment variables
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)
load_dotenv()

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '').strip()
ENDPOINT_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '').strip()
SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip()
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '').strip()
WEBSITE_BASE_URL = os.environ.get('WEBSITE_BASE_URL', 'https://www.jc-algos.com')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

PRICE_IDS = {
    'basic_monthly': os.environ.get('STRIPE_PRICE_MONTHLY', 'price_1SnjiK1JIZhXOZpFl8dhRnTu')
}


@app.route('/api/stripe/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'version': '3.6 (Trial Fix)',
        'stripe_configured': bool(stripe.api_key),
        'supabase_configured': bool(supabase)
    })


@app.route('/api/stripe/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        data = request.json or {}
        user_email = data.get('email')
        user_id = data.get('user_id')
        price_id = data.get('price_id', PRICE_IDS['basic_monthly'])

        logger.info(f"Attempting Checkout for: {user_email}")

        if not user_email or not user_id:
            return jsonify({'error': 'Missing email or user_id'}), 400

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=f'{WEBSITE_BASE_URL}/index.html',
            cancel_url=f'{WEBSITE_BASE_URL}/index.html',
            customer_email=user_email,
            subscription_data={
                'metadata': {'user_id': user_id}
            }
        )

        return jsonify({'id': checkout_session.id, 'url': checkout_session.url})

    except Exception as e:
        logger.error(f"CRITICAL STRIPE ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500


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

    # FIX: Handle trial/subscription created
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
    app.run(host='0.0.0.0', port=5007)
