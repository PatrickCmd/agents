import gradio as gr
from accounts import Account, get_share_price

# Global account instance for the single user demo
account = None

def create_account(user_id, initial_deposit):
    global account
    try:
        initial_deposit = float(initial_deposit) if initial_deposit else 0.0
        account = Account(user_id=user_id, initial_deposit=initial_deposit)
        return f"Account created for {user_id} with initial deposit: ${initial_deposit:.2f}"
    except Exception as e:
        return f"Error: {str(e)}"

def deposit_funds(amount):
    global account
    if account is None:
        return "Error: Please create an account first."
    try:
        amount = float(amount)
        account.deposit(amount)
        return f"Deposited ${amount:.2f}. New balance: ${account.get_cash_balance():.2f}"
    except Exception as e:
        return f"Error: {str(e)}"

def withdraw_funds(amount):
    global account
    if account is None:
        return "Error: Please create an account first."
    try:
        amount = float(amount)
        account.withdraw(amount)
        return f"Withdrew ${amount:.2f}. New balance: ${account.get_cash_balance():.2f}"
    except Exception as e:
        return f"Error: {str(e)}"

def buy_shares(symbol, quantity):
    global account
    if account is None:
        return "Error: Please create an account first."
    try:
        quantity = int(quantity)
        account.buy(symbol, quantity)
        price = get_share_price(symbol)
        return f"Bought {quantity} shares of {symbol} at ${price:.2f} each. New balance: ${account.get_cash_balance():.2f}"
    except Exception as e:
        return f"Error: {str(e)}"

def sell_shares(symbol, quantity):
    global account
    if account is None:
        return "Error: Please create an account first."
    try:
        quantity = int(quantity)
        account.sell(symbol, quantity)
        price = get_share_price(symbol)
        return f"Sold {quantity} shares of {symbol} at ${price:.2f} each. New balance: ${account.get_cash_balance():.2f}"
    except Exception as e:
        return f"Error: {str(e)}"

def get_holdings():
    global account
    if account is None:
        return "Error: Please create an account first."
    holdings = account.get_holdings()
    if not holdings:
        return "No holdings."
    result = "Current Holdings:\n"
    for symbol, qty in holdings.items():
        price = get_share_price(symbol)
        result += f"  {symbol}: {qty} shares (@ ${price:.2f} = ${qty * price:.2f})\n"
    return result

def get_portfolio_summary():
    global account
    if account is None:
        return "Error: Please create an account first."
    cash = account.get_cash_balance()
    portfolio_value = account.get_portfolio_value()
    profit_loss = account.get_profit_loss()
    pl_sign = "+" if profit_loss >= 0 else ""
    return f"Cash Balance: ${cash:.2f}\nPortfolio Value: ${portfolio_value:.2f}\nProfit/Loss: {pl_sign}${profit_loss:.2f}"

def get_transactions():
    global account
    if account is None:
        return "Error: Please create an account first."
    transactions = account.get_transaction_history()
    if not transactions:
        return "No transactions."
    result = "Transaction History:\n"
    for i, t in enumerate(transactions):
        if t.type in ['deposit', 'withdraw']:
            result += f"{i+1}. {t.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {t.type.upper()} - Balance: ${t.balance_after:.2f}\n"
        else:
            result += f"{i+1}. {t.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {t.type.upper()} {t.quantity} {t.symbol} @ ${t.price:.2f} - Balance: ${t.balance_after:.2f}\n"
    return result

with gr.Blocks(title="Trading Simulation Platform") as demo:
    gr.Markdown("# Trading Simulation Platform Demo")
    gr.Markdown("Available symbols: AAPL ($150), TSLA ($250), GOOGL ($2800)")
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Create Account")
            user_id_input = gr.Textbox(label="User ID", value="demo_user")
            initial_deposit_input = gr.Number(label="Initial Deposit ($)", value=10000)
            create_btn = gr.Button("Create Account")
            create_output = gr.Textbox(label="Result")
            create_btn.click(create_account, inputs=[user_id_input, initial_deposit_input], outputs=create_output)
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Deposit Funds")
            deposit_amount = gr.Number(label="Amount ($)", value=1000)
            deposit_btn = gr.Button("Deposit")
            deposit_output = gr.Textbox(label="Result")
            deposit_btn.click(deposit_funds, inputs=[deposit_amount], outputs=deposit_output)
        
        with gr.Column():
            gr.Markdown("### Withdraw Funds")
            withdraw_amount = gr.Number(label="Amount ($)", value=500)
            withdraw_btn = gr.Button("Withdraw")
            withdraw_output = gr.Textbox(label="Result")
            withdraw_btn.click(withdraw_funds, inputs=[withdraw_amount], outputs=withdraw_output)
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Buy Shares")
            buy_symbol = gr.Dropdown(label="Symbol", choices=["AAPL", "TSLA", "GOOGL"], value="AAPL")
            buy_quantity = gr.Number(label="Quantity", value=10)
            buy_btn = gr.Button("Buy")
            buy_output = gr.Textbox(label="Result")
            buy_btn.click(buy_shares, inputs=[buy_symbol, buy_quantity], outputs=buy_output)
        
        with gr.Column():
            gr.Markdown("### Sell Shares")
            sell_symbol = gr.Dropdown(label="Symbol", choices=["AAPL", "TSLA", "GOOGL"], value="AAPL")
            sell_quantity = gr.Number(label="Quantity", value=5)
            sell_btn = gr.Button("Sell")
            sell_output = gr.Textbox(label="Result")
            sell_btn.click(sell_shares, inputs=[sell_symbol, sell_quantity], outputs=sell_output)
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Portfolio Summary")
            summary_btn = gr.Button("Get Summary")
            summary_output = gr.Textbox(label="Summary", lines=4)
            summary_btn.click(get_portfolio_summary, outputs=summary_output)
        
        with gr.Column():
            gr.Markdown("### Holdings")
            holdings_btn = gr.Button("Get Holdings")
            holdings_output = gr.Textbox(label="Holdings", lines=4)
            holdings_btn.click(get_holdings, outputs=holdings_output)
    
    with gr.Row():
        gr.Markdown("### Transaction History")
    with gr.Row():
        transactions_btn = gr.Button("Get Transactions")
        transactions_output = gr.Textbox(label="Transactions", lines=10)
        transactions_btn.click(get_transactions, outputs=transactions_output)

if __name__ == "__main__":
    demo.launch()