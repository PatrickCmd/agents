from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime
import copy


def get_share_price(symbol: str) -> float:
    """
    Returns the current (test) price of a share for a given symbol.
    Test implementation: Returns fixed prices for 'AAPL', 'TSLA', 'GOOGL'.
    Raises ValueError for unknown symbols.
    """
    prices = {
        'AAPL': 150.0,
        'TSLA': 250.0,
        'GOOGL': 2800.0
    }
    if symbol not in prices:
        raise ValueError(f"Unknown symbol: {symbol}")
    return prices[symbol]


@dataclass
class Transaction:
    """
    Records all transactions (deposit, withdrawal, buy, sell).
    """
    timestamp: datetime
    type: str  # 'deposit', 'withdraw', 'buy', 'sell'
    symbol: Optional[str]
    quantity: Optional[int]
    price: Optional[float]
    balance_after: float
    holdings_after: Dict[str, int]


class Account:
    """
    Represents a trading simulation account.
    """
    
    def __init__(self, user_id: str, initial_deposit: float = 0.0):
        """
        Create a new account with a user_id and optional initial deposit.
        Initial deposit is processed as a transaction.
        """
        self.user_id = user_id
        self._cash_balance: float = 0.0
        self._holdings: Dict[str, int] = {}
        self._transactions: List[Transaction] = []
        self._total_deposits: float = 0.0
        
        if initial_deposit > 0:
            self.deposit(initial_deposit)
    
    def deposit(self, amount: float) -> None:
        """
        Deposit funds into the account.
        Args:
            amount: Positive float value to add.
        Raises:
            ValueError for non-positive or invalid deposit.
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        
        self._cash_balance += amount
        self._total_deposits += amount
        self._record_transaction(
            trans_type='deposit',
            symbol=None,
            quantity=None,
            price=None
        )
    
    def withdraw(self, amount: float) -> None:
        """
        Withdraw funds from the account.
        Args:
            amount: Positive float.
        Raises:
            ValueError if amount exceeds available free cash balance or is non-positive.
        """
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        if amount > self._cash_balance:
            raise ValueError("Insufficient funds for withdrawal.")
        
        self._cash_balance -= amount
        self._record_transaction(
            trans_type='withdraw',
            symbol=None,
            quantity=None,
            price=None
        )
    
    def buy(self, symbol: str, quantity: int) -> None:
        """
        Attempt to buy a quantity of shares at current price.
        Args:
            symbol: e.g., 'AAPL'
            quantity: Number of shares to buy.
        Raises:
            ValueError if insufficient funds or invalid input.
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")
        
        price = get_share_price(symbol)
        total_cost = price * quantity
        
        if total_cost > self._cash_balance:
            raise ValueError("Insufficient funds to buy shares.")
        
        self._cash_balance -= total_cost
        self._holdings[symbol] = self._holdings.get(symbol, 0) + quantity
        
        self._record_transaction(
            trans_type='buy',
            symbol=symbol,
            quantity=quantity,
            price=price
        )
    
    def sell(self, symbol: str, quantity: int) -> None:
        """
        Attempt to sell a quantity of shares at current price.
        Args:
            symbol: e.g., 'AAPL'
            quantity: Number of shares to sell.
        Raises:
            ValueError if insufficient shares or invalid input.
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")
        
        current_holding = self._holdings.get(symbol, 0)
        if quantity > current_holding:
            raise ValueError("Insufficient shares to sell.")
        
        price = get_share_price(symbol)
        total_value = price * quantity
        
        self._cash_balance += total_value
        self._holdings[symbol] -= quantity
        
        if self._holdings[symbol] == 0:
            del self._holdings[symbol]
        
        self._record_transaction(
            trans_type='sell',
            symbol=symbol,
            quantity=quantity,
            price=price
        )
    
    def get_holdings(self, at_index: Optional[int] = None) -> Dict[str, int]:
        """
        Returns a dict of holdings (symbol -> quantity).
        If at_index is given, returns holdings after that transaction.
        """
        if at_index is not None:
            _, holdings = self._get_snapshot(at_index)
            return copy.deepcopy(holdings)
        return copy.deepcopy(self._holdings)
    
    def get_cash_balance(self, at_index: Optional[int] = None) -> float:
        """
        Returns available cash balance.
        If at_index is given, returns balance after that transaction.
        """
        if at_index is not None:
            cash, _ = self._get_snapshot(at_index)
            return cash
        return self._cash_balance
    
    def get_portfolio_value(self, at_index: Optional[int] = None) -> float:
        """
        Returns total portfolio value (= cash + sum of shares*current_price).
        If at_index is set, uses holdings and cash after that transaction.
        """
        if at_index is not None:
            cash, holdings = self._get_snapshot(at_index)
        else:
            cash = self._cash_balance
            holdings = self._holdings
        
        shares_value = sum(
            get_share_price(symbol) * qty
            for symbol, qty in holdings.items()
        )
        return cash + shares_value
    
    def get_profit_loss(self, at_index: Optional[int] = None) -> float:
        """
        Returns profit or loss (current portfolio value - total deposits).
        If at_index is given, computes using that state.
        """
        portfolio_value = self.get_portfolio_value(at_index)
        
        # Calculate total deposits up to at_index if specified
        if at_index is not None:
            total_deposits = 0.0
            for i, t in enumerate(self._transactions[:at_index + 1]):
                if t.type == 'deposit':
                    if i == 0:
                        total_deposits += t.balance_after
                    else:
                        prev_balance = self._transactions[i-1].balance_after
                        total_deposits += (t.balance_after - prev_balance)
            return portfolio_value - total_deposits
        
        return portfolio_value - self._total_deposits
    
    def get_transaction_history(self) -> List[Transaction]:
        """
        Returns a list of all transaction records (Transaction instances).
        """
        return list(self._transactions)
    
    def _record_transaction(
        self,
        trans_type: str,
        symbol: Optional[str],
        quantity: Optional[int],
        price: Optional[float]
    ) -> None:
        """
        Records a transaction to the history, copies holdings/balance.
        """
        transaction = Transaction(
            timestamp=datetime.now(),
            type=trans_type,
            symbol=symbol,
            quantity=quantity,
            price=price,
            balance_after=self._cash_balance,
            holdings_after=copy.deepcopy(self._holdings)
        )
        self._transactions.append(transaction)
    
    def _get_snapshot(self, at_index: int) -> tuple:
        """
        Returns (cash, holdings) tuple for the state after the given transaction index.
        """
        if at_index < 0 or at_index >= len(self._transactions):
            raise ValueError(f"Invalid transaction index: {at_index}")
        
        transaction = self._transactions[at_index]
        return transaction.balance_after, transaction.holdings_after