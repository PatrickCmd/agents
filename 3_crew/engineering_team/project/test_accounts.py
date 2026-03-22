import unittest
from datetime import datetime
from accounts import get_share_price, Transaction, Account


class TestGetSharePrice(unittest.TestCase):
    def test_get_price_aapl(self):
        self.assertEqual(get_share_price('AAPL'), 150.0)
    
    def test_get_price_tsla(self):
        self.assertEqual(get_share_price('TSLA'), 250.0)
    
    def test_get_price_googl(self):
        self.assertEqual(get_share_price('GOOGL'), 2800.0)
    
    def test_unknown_symbol_raises_error(self):
        with self.assertRaises(ValueError) as context:
            get_share_price('UNKNOWN')
        self.assertIn('Unknown symbol', str(context.exception))


class TestTransaction(unittest.TestCase):
    def test_transaction_creation(self):
        now = datetime.now()
        trans = Transaction(
            timestamp=now,
            type='deposit',
            symbol=None,
            quantity=None,
            price=None,
            balance_after=1000.0,
            holdings_after={}
        )
        self.assertEqual(trans.timestamp, now)
        self.assertEqual(trans.type, 'deposit')
        self.assertIsNone(trans.symbol)
        self.assertEqual(trans.balance_after, 1000.0)


class TestAccountInitialization(unittest.TestCase):
    def test_account_creation_no_deposit(self):
        account = Account('user123')
        self.assertEqual(account.user_id, 'user123')
        self.assertEqual(account.get_cash_balance(), 0.0)
        self.assertEqual(account.get_holdings(), {})
    
    def test_account_creation_with_deposit(self):
        account = Account('user123', initial_deposit=1000.0)
        self.assertEqual(account.get_cash_balance(), 1000.0)
        self.assertEqual(len(account.get_transaction_history()), 1)


class TestDeposit(unittest.TestCase):
    def setUp(self):
        self.account = Account('user123')
    
    def test_deposit_positive_amount(self):
        self.account.deposit(500.0)
        self.assertEqual(self.account.get_cash_balance(), 500.0)
    
    def test_multiple_deposits(self):
        self.account.deposit(500.0)
        self.account.deposit(300.0)
        self.assertEqual(self.account.get_cash_balance(), 800.0)
    
    def test_deposit_records_transaction(self):
        self.account.deposit(500.0)
        history = self.account.get_transaction_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].type, 'deposit')
    
    def test_deposit_zero_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.deposit(0)
    
    def test_deposit_negative_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.deposit(-100.0)


class TestWithdraw(unittest.TestCase):
    def setUp(self):
        self.account = Account('user123', initial_deposit=1000.0)
    
    def test_withdraw_positive_amount(self):
        self.account.withdraw(300.0)
        self.assertEqual(self.account.get_cash_balance(), 700.0)
    
    def test_withdraw_all_funds(self):
        self.account.withdraw(1000.0)
        self.assertEqual(self.account.get_cash_balance(), 0.0)
    
    def test_withdraw_records_transaction(self):
        self.account.withdraw(300.0)
        history = self.account.get_transaction_history()
        self.assertEqual(history[-1].type, 'withdraw')
    
    def test_withdraw_zero_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.withdraw(0)
    
    def test_withdraw_negative_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.withdraw(-100.0)
    
    def test_withdraw_insufficient_funds_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.withdraw(1500.0)


class TestBuy(unittest.TestCase):
    def setUp(self):
        self.account = Account('user123', initial_deposit=5000.0)
    
    def test_buy_shares(self):
        self.account.buy('AAPL', 10)
        self.assertEqual(self.account.get_holdings(), {'AAPL': 10})
        self.assertEqual(self.account.get_cash_balance(), 3500.0)
    
    def test_buy_multiple_symbols(self):
        self.account.buy('AAPL', 10)
        self.account.buy('TSLA', 5)
        holdings = self.account.get_holdings()
        self.assertEqual(holdings['AAPL'], 10)
        self.assertEqual(holdings['TSLA'], 5)
    
    def test_buy_same_symbol_multiple_times(self):
        self.account.buy('AAPL', 10)
        self.account.buy('AAPL', 5)
        self.assertEqual(self.account.get_holdings()['AAPL'], 15)
    
    def test_buy_records_transaction(self):
        self.account.buy('AAPL', 10)
        history = self.account.get_transaction_history()
        self.assertEqual(history[-1].type, 'buy')
        self.assertEqual(history[-1].symbol, 'AAPL')
        self.assertEqual(history[-1].quantity, 10)
        self.assertEqual(history[-1].price, 150.0)
    
    def test_buy_zero_quantity_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.buy('AAPL', 0)
    
    def test_buy_negative_quantity_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.buy('AAPL', -5)
    
    def test_buy_insufficient_funds_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.buy('GOOGL', 10)
    
    def test_buy_unknown_symbol_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.buy('UNKNOWN', 10)


class TestSell(unittest.TestCase):
    def setUp(self):
        self.account = Account('user123', initial_deposit=5000.0)
        self.account.buy('AAPL', 20)
    
    def test_sell_shares(self):
        initial_balance = self.account.get_cash_balance()
        self.account.sell('AAPL', 10)
        self.assertEqual(self.account.get_holdings()['AAPL'], 10)
        self.assertEqual(self.account.get_cash_balance(), initial_balance + 1500.0)
    
    def test_sell_all_shares(self):
        self.account.sell('AAPL', 20)
        self.assertNotIn('AAPL', self.account.get_holdings())
    
    def test_sell_records_transaction(self):
        self.account.sell('AAPL', 10)
        history = self.account.get_transaction_history()
        self.assertEqual(history[-1].type, 'sell')
        self.assertEqual(history[-1].symbol, 'AAPL')
    
    def test_sell_zero_quantity_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.sell('AAPL', 0)
    
    def test_sell_negative_quantity_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.sell('AAPL', -5)
    
    def test_sell_insufficient_shares_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.sell('AAPL', 25)
    
    def test_sell_unowned_symbol_raises_error(self):
        with self.assertRaises(ValueError):
            self.account.sell('TSLA', 5)


class TestGetHoldings(unittest.TestCase):
    def setUp(self):
        self.account = Account('user123', initial_deposit=10000.0)
    
    def test_get_holdings_empty(self):
        self.assertEqual(self.account.get_holdings(), {})
    
    def test_get_holdings_with_stocks(self):
        self.account.buy('AAPL', 10)
        self.account.buy('TSLA', 5)
        holdings = self.account.get_holdings()
        self.assertEqual(holdings, {'AAPL': 10, 'TSLA': 5})
    
    def test_get_holdings_returns_copy(self):
        self.account.buy('AAPL', 10)
        holdings = self.account.get_holdings()
        holdings['AAPL'] = 999
        self.assertEqual(self.account.get_holdings()['AAPL'], 10)
    
    def test_get_holdings_at_index(self):
        self.account.buy('AAPL', 10)
        self.account.buy('TSLA', 5)
        holdings_at_1 = self.account.get_holdings(at_index=1)
        self.assertEqual(holdings_at_1, {'AAPL': 10})


class TestGetCashBalance(unittest.TestCase):
    def setUp(self):
        self.account = Account('user123', initial_deposit=1000.0)
    
    def test_get_cash_balance_initial(self):
        self.assertEqual(self.account.get_cash_balance(), 1000.0)
    
    def test_get_cash_balance_after_buy(self):
        self.account.buy('AAPL', 5)
        self.assertEqual(self.account.get_cash_balance(), 250.0)
    
    def test_get_cash_balance_at_index(self):
        self.account.buy('AAPL', 5)
        balance_at_0 = self.account.get_cash_balance(at_index=0)
        self.assertEqual(balance_at_0, 1000.0)


class TestGetPortfolioValue(unittest.TestCase):
    def setUp(self):
        self.account = Account('user123', initial_deposit=5000.0)
    
    def test_portfolio_value_cash_only(self):
        self.assertEqual(self.account.get_portfolio_value(), 5000.0)
    
    def test_portfolio_value_with_holdings(self):
        self.account.buy('AAPL', 10)
        expected = 3500.0 + (10 * 150.0)
        self.assertEqual(self.account.get_portfolio_value(), expected)
    
    def test_portfolio_value_at_index(self):
        self.account.buy('AAPL', 10)
        value_at_0 = self.account.get_portfolio_value(at_index=0)
        self.assertEqual(value_at_0, 5000.0)


class TestGetProfitLoss(unittest.TestCase):
    def setUp(self):
        self.account = Account('user123', initial_deposit=5000.0)
    
    def test_profit_loss_no_trades(self):
        self.assertEqual(self.account.get_profit_loss(), 0.0)
    
    def test_profit_loss_after_buy_no_change(self):
        self.account.buy('AAPL', 10)
        self.assertEqual(self.account.get_profit_loss(), 0.0)
    
    def test_profit_loss_at_index(self):
        self.account.buy('AAPL', 10)
        pl_at_0 = self.account.get_profit_loss(at_index=0)
        self.assertEqual(pl_at_0, 0.0)


class TestTransactionHistory(unittest.TestCase):
    def setUp(self):
        self.account = Account('user123', initial_deposit=5000.0)
    
    def test_transaction_history_initial(self):
        history = self.account.get_transaction_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].type, 'deposit')
    
    def test_transaction_history_multiple(self):
        self.account.buy('AAPL', 10)
        self.account.sell('AAPL', 5)
        history = self.account.get_transaction_history()
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0].type, 'deposit')
        self.assertEqual(history[1].type, 'buy')
        self.assertEqual(history[2].type, 'sell')


class TestSnapshotValidation(unittest.TestCase):
    def setUp(self):
        self.account = Account('user123', initial_deposit=1000.0)
    
    def test_invalid_negative_index(self):
        with self.assertRaises(ValueError):
            self.account.get_cash_balance(at_index=-1)
    
    def test_invalid_large_index(self):
        with self.assertRaises(ValueError):
            self.account.get_cash_balance(at_index=100)


if __name__ == '__main__':
    unittest.main()