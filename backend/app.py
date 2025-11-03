from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
import os

# Add shared directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

from config import SUPABASE_URL, SUPABASE_KEY, FLASK_ENV, FLASK_DEBUG
from supabase import create_client, Client

# Import existing modules
from services.db_utils import execute_db_action

# Create main Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Add WhatsApp webhook routes (both old and new for compatibility)
@app.route('/webhook', methods=['POST'])
@app.route('/reply_whatsapp', methods=['POST'])
def webhook():
    # Import here to avoid circular imports
    from reply_whatsapp import reply_whatsapp
    return reply_whatsapp()

# API Routes for Frontend
@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Get all transactions with optional filters"""
    try:
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        account = request.args.get('account')
        
        # Build query
        query = supabase.table("Transactions").select("*")
        
        if start_date:
            query = query.gte('created_at', start_date)
        if end_date:
            query = query.lte('created_at', end_date)
        if account:
            query = query.eq('account', account)
            
        query = query.order('created_at', desc=True).range(offset, offset + limit - 1)
        
        result = query.execute()
        
        # Get total count for pagination
        count_query = supabase.table("Transactions").select("*", count="exact")
        if start_date:
            count_query = count_query.gte('created_at', start_date)
        if end_date:
            count_query = count_query.lte('created_at', end_date)
        if account:
            count_query = count_query.eq('account', account)
        
        count_result = count_query.execute()
        total_count = count_result.count if hasattr(count_result, 'count') else len(result.data)
        
        return jsonify({
            'success': True,
            'data': result.data,
            'pagination': {
                'page': (offset // limit) + 1,
                'limit': limit,
                'total': total_count,
                'pages': (total_count + limit - 1) // limit,
                'has_next': offset + limit < total_count,
                'has_prev': offset > 0
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts with balances"""
    try:
        # Get query parameters for pagination
        limit = request.args.get('limit', 10, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Get accounts with pagination
        result = supabase.table("Accounts").select("*").range(offset, offset + limit - 1).execute()
        
        # Get total count
        count_result = supabase.table("Accounts").select("*", count="exact").execute()
        total_count = count_result.count if hasattr(count_result, 'count') else len(result.data)
        
        return jsonify({
            'success': True,
            'data': result.data,
            'pagination': {
                'page': (offset // limit) + 1,
                'limit': limit,
                'total': total_count,
                'pages': (total_count + limit - 1) // limit,
                'has_next': offset + limit < total_count,
                'has_prev': offset > 0
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics for dashboard"""
    try:
        # Get total balance
        accounts_result = supabase.table("Accounts").select("sum").execute()
        total_balance = sum(account['sum'] for account in accounts_result.data) if accounts_result.data else 0
        
        # Get transaction count
        transactions_result = supabase.table("Transactions").select("id").execute()
        transaction_count = len(transactions_result.data) if transactions_result.data else 0
        
        # Get recent transactions
        recent_result = supabase.table("Transactions").select("*").order('created_at', desc=True).limit(5).execute()
        
        return jsonify({
            'success': True,
            'data': {
                'total_balance': total_balance,
                'transaction_count': transaction_count,
                'recent_transactions': recent_result.data if recent_result.data else []
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    """Add a new transaction"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['amount', 'account']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Insert transaction
        result = supabase.table("Transactions").insert(data).execute()
        
        if result.data:
            return jsonify({
                'success': True,
                'data': result.data[0]
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to insert transaction'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=FLASK_DEBUG, host='0.0.0.0', port=3000)
